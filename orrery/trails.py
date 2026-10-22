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
        self._trails: list[Deque[Vec2]] = [
            deque([body.pos], maxlen=limit) for body in world.bodies
        ]
        self._steps = 0

    @property
    def trails(self) -> tuple[Deque[Vec2], ...]:
        return tuple(self._trails)

    def record(self, world: World) -> None:
        if len(world.bodies) != len(self._trails):
            raise ValueError("the world changed its body count")
        for trail, body in zip(self._trails, world.bodies):
            trail.append(body.pos)

    def advance(self, world: World, dt: float, steps: int, every: int = 1) -> None:
        if steps < 0:
            raise ValueError("steps cannot be negative")
        if every < 1:
            raise ValueError("the sampling interval must be at least one step")
        for _ in range(steps):
            world.step(dt)
            self._steps += 1
            if self._steps % every == 0:
                self.record(world)

    def advance_to(self, world: World, target: float, dt: float, every: int = 1) -> None:
        if not math.isfinite(target):
            raise ValueError("the target time must be finite")
        if every < 1:
            raise ValueError("the sampling interval must be at least one step")
        while world.time < target - 1e-12:
            remaining = target - world.time
            world.step(dt if remaining > dt else remaining)
            self._steps += 1
            if self._steps % every == 0:
                self.record(world)
