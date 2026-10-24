"""The built-in worlds.

Solar-system scenarios use astronomical units, days and solar masses, so the gravitational
constant is the Gaussian one. The figure-eight choreography uses its own natural units (G = 1,
three unit masses), which keeps its published initial conditions exact.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
import math

from .sim import Body, Vec2

YEAR_DAYS = 365.2568983
G_SOLAR = 4.0 * math.pi**2 / YEAR_DAYS**2
AU_PER_DAY_TO_KM_PER_S = 149_597_870.7 / 86_400.0


@dataclass(frozen=True, slots=True)
class Scenario:
    """A named initial state plus the knobs the player needs to present it."""

    key: str
    title: str
    description: str
    g: float
    dt: float
    span: float
    extent: tuple[float, float]
    bodies: tuple[Body, ...]
    steps_per_frame: int
    trail_length: int
    record_every: int
    default_frames: int
    export_until: float
    time_unit: str
    distance_unit: str
    mass_unit: str
    speed_unit: str
    speed_scale: float
    c: float | None = None

    def __post_init__(self) -> None:
        if not self.key or not self.title or not self.description:
            raise ValueError("a scenario needs a key, title and description")
        if not math.isfinite(self.g) or self.g <= 0.0:
            raise ValueError(f"scenario '{self.key}' needs a positive finite G")
        if self.c is not None and (not math.isfinite(self.c) or self.c <= 0.0):
            raise ValueError(f"scenario '{self.key}' needs a positive finite speed of light")
        if not math.isfinite(self.dt) or self.dt <= 0.0:
            raise ValueError(f"scenario '{self.key}' needs a positive finite time step")
        if not math.isfinite(self.span) or self.span <= 0.0:
            raise ValueError(f"scenario '{self.key}' needs a positive finite view span")
        if len(self.extent) != 2 or not all(
            math.isfinite(value) and value > 0.0 for value in self.extent
        ):
            raise ValueError(f"scenario '{self.key}' needs two positive view extents")
        if not self.bodies:
            raise ValueError(f"scenario '{self.key}' needs at least one body")
        for body in self.bodies:
            if abs(body.pos.x) > self.extent[0] or abs(body.pos.y) > self.extent[1]:
                raise ValueError(
                    f"scenario '{self.key}' body '{body.name}' lies outside its extent"
                )
        names = set()
        symbols = set()
        for body in self.bodies:
            if body.name in names:
                raise ValueError(f"scenario '{self.key}' repeats the name '{body.name}'")
            if body.symbol in symbols:
                raise ValueError(f"scenario '{self.key}' repeats the symbol '{body.symbol}'")
            if len(body.symbol) != 1 or not body.symbol.isascii() or not body.symbol.isprintable():
                raise ValueError(f"scenario '{self.key}' needs one printable ASCII symbol per body")
            names.add(body.name)
            symbols.add(body.symbol)
        for value, label in ((self.steps_per_frame, "steps_per_frame"),
                             (self.trail_length, "trail_length"),
                             (self.record_every, "record_every"),
                             (self.default_frames, "default_frames")):
            if value < 1:
                raise ValueError(f"scenario '{self.key}' needs {label} >= 1")
        if not math.isfinite(self.export_until) or self.export_until <= 0.0:
            raise ValueError(f"scenario '{self.key}' needs a positive finite export window")
        if self.speed_scale <= 0.0:
            raise ValueError(f"scenario '{self.key}' needs a positive speed scale")


def _rotate(vector: Vec2, angle: float) -> Vec2:
    cosine = math.cos(angle)
    sine = math.sin(angle)
    return Vec2(vector.x * cosine - vector.y * sine, vector.x * sine + vector.y * cosine)


def _center_and_zero_momentum(bodies: tuple[Body, ...]) -> tuple[Body, ...]:
    """Move the origin to the barycentre and remove any net drift."""
    total_mass = math.fsum(body.mass for body in bodies)
    center = Vec2(
        math.fsum(body.mass * body.pos.x for body in bodies) / total_mass,
        math.fsum(body.mass * body.pos.y for body in bodies) / total_mass,
    )
    drift = Vec2(
        math.fsum(body.mass * body.vel.x for body in bodies) / total_mass,
        math.fsum(body.mass * body.vel.y for body in bodies) / total_mass,
    )
    return tuple(replace(body, pos=body.pos - center, vel=body.vel - drift) for body in bodies)


def _planet(name: str, mass: float, semi_major: float, eccentricity: float,
            angle_degrees: float, symbol: str, color: str) -> Body:
    """A planet released at perihelion, with its orbit rotated around the Sun."""
    mu = G_SOLAR * (1.0 + mass)
    perihelion = semi_major * (1.0 - eccentricity)
    speed = math.sqrt(mu * (1.0 + eccentricity) / perihelion)
    angle = math.radians(angle_degrees)
    return Body(
        name=name,
        mass=mass,
        pos=_rotate(Vec2(perihelion, 0.0), angle),
        vel=_rotate(Vec2(0.0, speed), angle),
        symbol=symbol,
        color=color,
    )


def _solar() -> Scenario:
    sun = Body("Sun", 1.0, Vec2(), Vec2(), "@", "yellow")
    planets = (
        _planet("Mercury", 1.660120e-7, 0.387098, 0.205630, 0.0, "m", "gray"),
        _planet("Venus", 2.447838e-6, 0.723332, 0.006772, 70.0, "v", "gold"),
        _planet("Earth", 3.003489e-6, 1.000000, 0.016708, 160.0, "E", "blue"),
        _planet("Mars", 3.227151e-7, 1.523679, 0.093400, 250.0, "M", "red"),
    )
    return Scenario(
        key="solar",
        title="Inner Solar System",
        description=(
            "Mercury, Venus, Earth and Mars on their real eccentric orbits around the Sun. "
            "Orbits are started at perihelion and rotated so the ellipses do not overlap visually."
        ),
        g=G_SOLAR,
        dt=0.2,
        span=3.6,
        extent=(1.75, 1.70),
        bodies=_center_and_zero_momentum((sun, *planets)),
        steps_per_frame=8,
        trail_length=2000,
        record_every=1,
        default_frames=220,
        export_until=YEAR_DAYS,
        time_unit="d",
        distance_unit="AU",
        mass_unit="Msun",
        speed_unit="km/s",
        speed_scale=AU_PER_DAY_TO_KM_PER_S,
        c=173.1446,
    )


def _figure_eight() -> Scenario:
    """Chenciner-Montgomery three-body choreography in natural units."""
    bodies = (
        Body("Alpha", 1.0, Vec2(0.97000436, -0.24308753),
             Vec2(0.4662036850, 0.4323657300), "A", "cyan"),
        Body("Beta", 1.0, Vec2(-0.97000436, 0.24308753),
             Vec2(0.4662036850, 0.4323657300), "B", "magenta"),
        Body("Gamma", 1.0, Vec2(0.0, 0.0),
             Vec2(-0.93240737, -0.86473146), "C", "yellow"),
    )
    return Scenario(
        key="figure-eight",
        title="Figure-Eight Choreography",
        description=(
            "Three equal masses chase one another around a single figure-eight curve. "
            "This is the celebrated Chenciner-Montgomery periodic solution: no body ever "
            "escapes, and the pattern repeats after about 6.33 time units."
        ),
        g=1.0,
        dt=0.001,
        span=1.3,
        extent=(1.0, 0.30),
        bodies=bodies,
        steps_per_frame=20,
        trail_length=4800,
        record_every=1,
        default_frames=320,
        export_until=6.32591398,
        time_unit="t",
        distance_unit="u",
        mass_unit="m",
        speed_unit="u/t",
        speed_scale=1.0,
        c=100.0,
    )


def _binary() -> Scenario:
    separation = 0.2
    star_mass = 0.5
    relative_speed = math.sqrt(G_SOLAR * (2.0 * star_mass) / separation)
    planet_distance = 1.3
    planet_mass = 0.001
    bodies = (
        Body("Aster", star_mass, Vec2(-separation / 2.0, 0.0),
             Vec2(0.0, -relative_speed / 2.0), "A", "cyan"),
        Body("Boreas", star_mass, Vec2(separation / 2.0, 0.0),
             Vec2(0.0, relative_speed / 2.0), "B", "magenta"),
        Body("Pale", planet_mass, Vec2(planet_distance, 0.0),
             Vec2(0.0, math.sqrt(G_SOLAR * (2.0 * star_mass + planet_mass) / planet_distance)),
             "P", "blue"),
    )
    return Scenario(
        key="binary",
        title="Circumbinary Planet",
        description=(
            "Two half-solar-mass stars orbit their common barycentre every ~33 days while a "
            "Jupiter-mass planet circles both of them at 1.3 AU. The stars' motion is the wobble "
            "that radial-velocity surveys look for."
        ),
        g=G_SOLAR,
        dt=0.01,
        span=3.6,
        extent=(1.40, 1.40),
        bodies=_center_and_zero_momentum(bodies),
        steps_per_frame=80,
        trail_length=6400,
        record_every=1,
        default_frames=160,
        export_until=YEAR_DAYS,
        time_unit="d",
        distance_unit="AU",
        mass_unit="Msun",
        speed_unit="km/s",
        speed_scale=AU_PER_DAY_TO_KM_PER_S,
        c=173.1446,
    )


def _trojans() -> Scenario:
    jupiter_mass = 9.5458e-4
    orbit_radius = 5.2038
    orbit_speed = math.sqrt(G_SOLAR * (1.0 + jupiter_mass) / orbit_radius)
    asteroid_mass = 1e-8
    bodies = [
        Body("Sun", 1.0, Vec2(), Vec2(), "@", "yellow"),
        Body("Jupiter", jupiter_mass, Vec2(orbit_radius, 0.0),
             Vec2(0.0, orbit_speed), "J", "orange"),
    ]
    for name, angle_degrees, symbol, color in (
        ("Achilles", 60.0, "a", "cyan"),
        ("Patroclus", -60.0, "b", "green"),
    ):
        angle = math.radians(angle_degrees)
        bodies.append(
            Body(
                name=name,
                mass=asteroid_mass,
                pos=_rotate(Vec2(orbit_radius, 0.0), angle),
                vel=_rotate(Vec2(0.0, orbit_speed), angle),
                symbol=symbol,
                color=color,
            )
        )
    return Scenario(
        key="trojans",
        title="Jupiter Trojans",
        description=(
            "Asteroids Achilles and Patroclus sit at Jupiter's L4 and L5 Lagrange points, "
            "60 degrees ahead of and behind the planet. In the Sun-Jupiter system those "
            "triangular points are stable, so the asteroids keep station for centuries."
        ),
        g=G_SOLAR,
        dt=0.5,
        span=13.0,
        extent=(5.40, 4.70),
        bodies=_center_and_zero_momentum(tuple(bodies)),
        steps_per_frame=5,
        trail_length=1600,
        record_every=1,
        default_frames=220,
        export_until=YEAR_DAYS,
        time_unit="d",
        distance_unit="AU",
        mass_unit="Msun",
        speed_unit="km/s",
        speed_scale=AU_PER_DAY_TO_KM_PER_S,
        c=173.1446,
    )


def _pythagorean() -> Scenario:
    """The classic 3-4-5 three-body problem: rest, a close encounter, then ejection."""
    bodies = (
        Body("Three", 3.0, Vec2(1.0, 3.0), Vec2(), "3", "cyan"),
        Body("Four", 4.0, Vec2(-2.0, -1.0), Vec2(), "4", "magenta"),
        Body("Five", 5.0, Vec2(1.0, -1.0), Vec2(), "5", "yellow"),
    )
    return Scenario(
        key="pythagorean",
        title="Pythagorean Chaos",
        description=(
            "The classic 3-4-5 three-body problem: three masses at rest at the corners of a "
            "right triangle. Their first close encounter is chaotic and slings two of them "
            "outward. The small time step resolves the encounter."
        ),
        g=1.0,
        dt=0.0001,
        span=10.0,
        extent=(5.0, 5.0),
        bodies=_center_and_zero_momentum(bodies),
        steps_per_frame=100,
        trail_length=10000,
        record_every=2,
        default_frames=220,
        export_until=2.2,
        time_unit="t",
        distance_unit="u",
        mass_unit="m",
        speed_unit="u/t",
        speed_scale=1.0,
        c=100.0,
    )


def _lagrange() -> Scenario:
    """Lagrange's 1772 equilateral pinwheel: three equal masses in a rigid rotating triangle."""
    s = math.sqrt(3.0)
    v = 1.0 / (3.0 ** 0.25)
    bodies = (
        Body("Alpha", 1.0, Vec2(1.0, 0.0), Vec2(0.0, v), "A", "cyan"),
        Body("Beta", 1.0, Vec2(-0.5, s / 2.0), Vec2(-v * s / 2.0, -v * 0.5), "B", "yellow"),
        Body("Gamma", 1.0, Vec2(-0.5, -s / 2.0), Vec2(v * s / 2.0, -v * 0.5), "C", "magenta"),
    )
    return Scenario(
        key="lagrange",
        title="Lagrange Equilateral Pinwheel",
        description=(
            "Lagrange's 1772 three-body solution: three equal masses at the vertices of an "
            "equilateral triangle rotate about their common barycentre in rigid harmony."
        ),
        g=1.0,
        dt=0.001,
        span=3.0,
        extent=(1.2, 1.2),
        bodies=bodies,
        steps_per_frame=40,
        trail_length=4000,
        record_every=1,
        default_frames=210,
        export_until=2.0 * math.pi * (3.0 ** 0.25),
        time_unit="t",
        distance_unit="u",
        mass_unit="m",
        speed_unit="u/t",
        speed_scale=1.0,
        c=100.0,
    )


SCENARIOS: dict[str, Scenario] = {
    scenario.key: scenario
    for scenario in (
        _solar(),
        _figure_eight(),
        _binary(),
        _trojans(),
        _pythagorean(),
        _lagrange(),
    )
}

_ALIASES = {
    "inner": "solar",
    "solar-system": "solar",
    "inner-solar-system": "solar",
    "figure-8": "figure-eight",
    "figure8": "figure-eight",
    "eight": "figure-eight",
    "three-body": "figure-eight",
    "circumbinary": "binary",
    "trojan": "trojans",
    "jupiter-trojans": "trojans",
    "pythagoras": "pythagorean",
    "chaos": "pythagorean",
    "three-four-five": "pythagorean",
    "triangle": "lagrange",
    "equilateral": "lagrange",
    "pinwheel": "lagrange",
}


def scenario_keys() -> tuple[str, ...]:
    return tuple(SCENARIOS)


def get_scenario(name: str) -> Scenario:
    """Resolve a key or a forgiving alias; raise KeyError when nothing matches."""
    normalized = name.strip().lower().replace("_", "-").replace(" ", "-")
    key = _ALIASES.get(normalized, normalized)  # aikit:allow-secret scenario key, not a credential
    try:
        return SCENARIOS[key]
    except KeyError:
        raise KeyError(name) from None
