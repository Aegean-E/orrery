"""Bounded, sampled position history for drawing orbit trails."""

from __future__ import annotations

from collections import deque
import math
from typing import Deque

from .sim import Vec2, World


class TrailRecorder:
    """Keep one bounded deque of past positions per body, sampled every N steps."""

    def __init__(self, world: World, limit: int) -> None:
        if limit < 0:
            raise ValueError("the trail limit cannot be negative")
        self._limit = limit
        self._trails: list[Deque[Vec2]] = [
            deque([body.pos], maxlen=limit) for body in world.bodies
        ]
        self._steps = 0

    @property
    def trails(self) -> tuple[Deque[Vec2], ...]:
        return tuple(self._trails)

    def sync(self, world: World) -> None:
        """Synchronize trail history buffers when the world body count changes."""
        if len(self._trails) > len(world.bodies):
            self._trails = self._trails[:len(world.bodies)]
        elif len(self._trails) < len(world.bodies):
            for i in range(len(self._trails), len(world.bodies)):
                self._trails.append(deque([world.bodies[i].pos], maxlen=self._limit))

    def record(self, world: World) -> None:
        if len(world.bodies) != len(self._trails):
            self.sync(world)
        for trail, body in zip(self._trails, world.bodies):
            trail.append(body.pos)

    def clear(self, world: World | None = None) -> None:
        """Clear historical trail samples, seeding with current positions if world is given."""
        for index, trail in enumerate(self._trails):
            trail.clear()
            if world is not None and index < len(world.bodies):
                trail.append(world.bodies[index].pos)

    def advance(self, world: World, dt: float, steps: int, every: int = 1,
                merge_radius: float = 0.0) -> list[tuple[str, str, str]]:
        if steps < 0:
            raise ValueError("steps cannot be negative")
        if every < 1:
            raise ValueError("the sampling interval must be at least one step")
        collisions = []
        for _ in range(steps):
            world.step(dt)
            if merge_radius > 0.0:
                events = world.resolve_collisions(merge_radius)
                if events:
                    collisions.extend(events)
                    self.sync(world)
            self._steps += 1
            if self._steps % every == 0:
                self.record(world)
        return collisions

    def advance_to(self, world: World, target: float, dt: float, every: int = 1,
                   merge_radius: float = 0.0) -> list[tuple[str, str, str]]:
        if not math.isfinite(target):
            raise ValueError("the target time must be finite")
        if target < world.time - 1e-12:
            raise ValueError("cannot travel backwards in time")
        if every < 1:
            raise ValueError("the sampling interval must be at least one step")
        collisions: list[tuple[str, str, str]] = []
        while world.time < target - 1e-12:
            remaining = target - world.time
            world.step(dt if remaining > dt else remaining)
            if merge_radius > 0.0:
                events = world.resolve_collisions(merge_radius)
                if events:
                    collisions.extend(events)
                    self.sync(world)
            self._steps += 1
            if self._steps % every == 0:
                self.record(world)
        return collisions
