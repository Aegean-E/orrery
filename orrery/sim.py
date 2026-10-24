"""Gravity, bodies and a symplectic leapfrog integrator.

Everything here is unit-agnostic. A :class:`World` needs a gravitational constant and a set of
bodies; the scenarios choose units. The integrator is kick-drift-kick leapfrog, which is
time-reversible and keeps orbital energy bounded instead of drifting secularly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Sequence


@dataclass(frozen=True, slots=True)
class Vec2:
    """A point or vector in the plane."""

    x: float = 0.0
    y: float = 0.0

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Vec2":
        return Vec2(self.x * scalar, self.y * scalar)

    def __rmul__(self, scalar: float) -> "Vec2":
        return self * scalar

    def __truediv__(self, scalar: float) -> "Vec2":
        return Vec2(self.x / scalar, self.y / scalar)

    def __neg__(self) -> "Vec2":
        return Vec2(-self.x, -self.y)

    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.y * other.y

    def norm_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def norm(self) -> float:
        return math.hypot(self.x, self.y)

    def distance_to(self, other: "Vec2") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


@dataclass(frozen=True, slots=True)
class Body:
    """An immutable snapshot of one gravitating body."""

    name: str
    mass: float
    pos: Vec2
    vel: Vec2
    symbol: str = "o"
    color: str = "white"


@dataclass(frozen=True, slots=True)
class Orbit:
    """Osculating elements of one body around a chosen primary, in world units."""

    semi_major: float | None
    eccentricity: float | None
    period: float | None


def _accelerations(bodies: Sequence[Body], g: float,
                   c: float | None = None) -> tuple[Vec2, ...]:
    """Pairwise Newtonian acceleration on every body, with optional 1PN general relativity."""
    count = len(bodies)
    ax = [0.0] * count
    ay = [0.0] * count
    c2 = c * c if (c is not None and c > 0.0) else None
    for i in range(count - 1):
        first = bodies[i]
        for j in range(i + 1, count):
            second = bodies[j]
            dx = second.pos.x - first.pos.x
            dy = second.pos.y - first.pos.y
            r2 = dx * dx + dy * dy
            if r2 <= 0.0:
                continue
            r = math.sqrt(r2)
            inverse_r3 = 1.0 / (r2 * r)
            pull = g * inverse_r3
            if c2 is not None:
                dvx = first.vel.x - second.vel.x
                dvy = first.vel.y - second.vel.y
                v2 = dvx * dvx + dvy * dvy
                rv_dot = dx * dvx + dy * dvy
                phi = g * (first.mass + second.mass) / r
                factor_r = (4.0 * phi - v2) / c2
                factor_v = 4.0 * rv_dot / c2
                a_ix = pull * second.mass * (dx * (1.0 + factor_r) - dvx * factor_v)
                a_iy = pull * second.mass * (dy * (1.0 + factor_r) - dvy * factor_v)
                a_jx = pull * first.mass * (dx * (1.0 + factor_r) - dvx * factor_v)
                a_jy = pull * first.mass * (dy * (1.0 + factor_r) - dvy * factor_v)
                ax[i] += a_ix
                ay[i] += a_iy
                ax[j] -= a_jx
                ay[j] -= a_jy
            else:
                ax[i] += pull * second.mass * dx
                ay[i] += pull * second.mass * dy
                ax[j] -= pull * first.mass * dx
                ay[j] -= pull * first.mass * dy
    return tuple(Vec2(ax[i], ay[i]) for i in range(count))


@dataclass(slots=True)
class World:
    """A mutable simulation clock over a tuple of immutable bodies."""

    bodies: tuple[Body, ...]
    g: float
    time: float = 0.0
    c: float | None = None

    def __post_init__(self) -> None:
        if not math.isfinite(self.g) or self.g <= 0.0:
            raise ValueError("the gravitational constant must be a positive finite number")
        if self.c is not None and (not math.isfinite(self.c) or self.c <= 0.0):
            raise ValueError("the speed of light must be a positive finite number")
        if not self.bodies:
            raise ValueError("a world needs at least one body")
        names = set()
        for body in self.bodies:
            if not math.isfinite(body.mass) or body.mass <= 0.0:
                raise ValueError(f"body '{body.name}' must have a positive finite mass")
            if not all(math.isfinite(value) for value in
                       (body.pos.x, body.pos.y, body.vel.x, body.vel.y)):
                raise ValueError(f"body '{body.name}' has a non-finite state")
            if body.name in names:
                raise ValueError(f"duplicate body name '{body.name}'")
            names.add(body.name)
        if not math.isfinite(self.time):
            raise ValueError("time must be finite")

    def accelerations(self) -> tuple[Vec2, ...]:
        return _accelerations(self.bodies, self.g, self.c)

    def step(self, dt: float) -> None:
        """Advance one kick-drift-kick leapfrog step of length ``dt``."""
        if not math.isfinite(dt) or dt <= 0.0:
            raise ValueError("the time step must be a positive finite number")
        half = dt * 0.5
        start = _accelerations(self.bodies, self.g, self.c)
        drifted = tuple(
            replace(
                body,
                pos=Vec2(
                    body.pos.x + (body.vel.x + acc.x * half) * dt,
                    body.pos.y + (body.vel.y + acc.y * half) * dt,
                ),
                vel=Vec2(body.vel.x + acc.x * half, body.vel.y + acc.y * half),
            )
            for body, acc in zip(self.bodies, start)
        )
        end = _accelerations(drifted, self.g, self.c)
        self.bodies = tuple(
            replace(body, vel=Vec2(body.vel.x + acc.x * half, body.vel.y + acc.y * half))
            for body, acc in zip(drifted, end)
        )
        self.time += dt

    def resolve_collisions(self, merge_radius: float = 0.01) -> list[tuple[str, str, str]]:
        """Inelastically merge bodies closer than merge_radius, conserving momentum."""
        if merge_radius <= 0.0 or len(self.bodies) <= 1:
            return []
        bodies_list = list(self.bodies)
        events: list[tuple[str, str, str]] = []
        i = 0
        while i < len(bodies_list):
            j = i + 1
            merged_any = False
            while j < len(bodies_list):
                b1 = bodies_list[i]
                b2 = bodies_list[j]
                if b1.pos.distance_to(b2.pos) <= merge_radius:
                    total_m = b1.mass + b2.mass
                    pos = (b1.pos * b1.mass + b2.pos * b2.mass) / total_m
                    vel = (b1.vel * b1.mass + b2.vel * b2.mass) / total_m
                    primary, secondary = (b1, b2) if b1.mass >= b2.mass else (b2, b1)
                    new_body = Body(
                        name=primary.name,
                        mass=total_m,
                        pos=pos,
                        vel=vel,
                        symbol=primary.symbol,
                        color=primary.color,
                    )
                    events.append((primary.name, secondary.name, new_body.name))
                    bodies_list[i] = new_body
                    bodies_list.pop(j)
                    merged_any = True
                else:
                    j += 1
            if not merged_any:
                i += 1
        if events:
            self.bodies = tuple(bodies_list)
        return events

    def advance(self, dt: float, steps: int, merge_radius: float = 0.0) -> list[tuple[str, str, str]]:
        if steps < 0:
            raise ValueError("steps cannot be negative")
        events: list[tuple[str, str, str]] = []
        for _ in range(steps):
            self.step(dt)
            if merge_radius > 0.0:
                step_events = self.resolve_collisions(merge_radius)
                if step_events:
                    events.extend(step_events)
        return events

    def advance_to(self, target: float, dt: float, merge_radius: float = 0.0) -> list[tuple[str, str, str]]:
        """Integrate to ``target``, ending with a shorter step when needed."""
        if not math.isfinite(target):
            raise ValueError("the target time must be finite")
        if target < self.time - 1e-12:
            raise ValueError("cannot travel backwards in time")
        events: list[tuple[str, str, str]] = []
        while self.time < target - 1e-12:
            remaining = target - self.time
            self.step(dt if remaining > dt else remaining)
            if merge_radius > 0.0:
                step_events = self.resolve_collisions(merge_radius)
                if step_events:
                    events.extend(step_events)
        return events

    @property
    def total_mass(self) -> float:
        return math.fsum(body.mass for body in self.bodies)

    def momentum(self) -> Vec2:
        return Vec2(
            math.fsum(body.mass * body.vel.x for body in self.bodies),
            math.fsum(body.mass * body.vel.y for body in self.bodies),
        )

    def center_of_mass(self) -> Vec2:
        total = self.total_mass
        return Vec2(
            math.fsum(body.mass * body.pos.x for body in self.bodies) / total,
            math.fsum(body.mass * body.pos.y for body in self.bodies) / total,
        )

    def kinetic_energy(self) -> float:
        return math.fsum(0.5 * body.mass * body.vel.norm_sq() for body in self.bodies)

    def potential_energy(self) -> float:
        total = 0.0
        for i in range(len(self.bodies) - 1):
            for j in range(i + 1, len(self.bodies)):
                separation = self.bodies[i].pos.distance_to(self.bodies[j].pos)
                if separation > 0.0:
                    total -= self.g * self.bodies[i].mass * self.bodies[j].mass / separation
        return total

    def total_energy(self) -> float:
        return self.kinetic_energy() + self.potential_energy()

    def angular_momentum(self) -> float:
        return math.fsum(
            body.mass * (body.pos.x * body.vel.y - body.pos.y * body.vel.x)
            for body in self.bodies
        )

    def energy_drift(self, initial_energy: float) -> float:
        if initial_energy == 0.0:
            return 0.0
        return (self.total_energy() - initial_energy) / abs(initial_energy)


def orbital_elements(primary: Body, body: Body, g: float) -> Orbit:
    """Osculating semi-major axis, eccentricity and period of ``body`` around ``primary``."""
    relative_position = body.pos - primary.pos
    relative_velocity = body.vel - primary.vel
    radius = relative_position.norm()
    mu = g * (primary.mass + body.mass)
    if radius <= 0.0 or mu <= 0.0:
        return Orbit(None, None, None)
    speed_sq = relative_velocity.norm_sq()
    specific_energy = 0.5 * speed_sq - mu / radius
    energy_scale = mu / radius
    # A tiny negative energy is a numerical parabola, not a gigantic ellipse.
    if specific_energy < -1e-12 * energy_scale:
        semi_major = -mu / (2.0 * specific_energy)
    else:
        semi_major = None
    eccentricity_vector = (
        relative_position * (speed_sq / mu - 1.0 / radius)
        - relative_velocity * (relative_position.dot(relative_velocity) / mu)
    )
    eccentricity = eccentricity_vector.norm()
    period = None
    if semi_major is not None and semi_major > 0.0:
        period = 2.0 * math.pi * math.sqrt(semi_major**3 / mu)
    return Orbit(semi_major, eccentricity, period)
