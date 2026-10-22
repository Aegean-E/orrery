"""Turn a world into a rectangular block of terminal cells.

The viewport corrects for a terminal cell being roughly twice as tall as it is wide, so a
circular orbit looks circular instead of squashed. Rendering is pure: it returns lines and never
touches the terminal, which keeps it easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from .sim import Vec2, World

ANSI = {
    "yellow": "\x1b[93m",
    "gold": "\x1b[33m",
    "gray": "\x1b[90m",
    "blue": "\x1b[94m",
    "red": "\x1b[91m",
    "orange": "\x1b[38;5;208m",
    "cyan": "\x1b[96m",
    "magenta": "\x1b[95m",
    "green": "\x1b[92m",
    "white": "\x1b[97m",
}
RESET = "\x1b[0m"
TRAIL_UNICODE = "·"
TRAIL_ASCII = "."


@dataclass(frozen=True, slots=True)
class Viewport:
    """A rectangular map from world units to terminal cells."""

    width: int
    height: int
    span: float
    center: Vec2 = Vec2()

    def __post_init__(self) -> None:
        if self.width < 5 or self.height < 3:
            raise ValueError("the viewport needs at least 5 columns and 3 rows")
        if not math.isfinite(self.span) or self.span <= 0.0:
            raise ValueError("the viewport span must be a positive finite number")
        if not (math.isfinite(self.center.x) and math.isfinite(self.center.y)):
            raise ValueError("the viewport centre must be finite")

    @property
    def rows_per_unit(self) -> float:
        return (self.height - 1) / self.span

    @property
    def cols_per_unit(self) -> float:
        return 2.0 * self.rows_per_unit

    def cell(self, point: Vec2) -> tuple[int, int] | None:
        """Return ``(column, row)`` for a world point, or ``None`` when off-screen."""
        column = round((self.width - 1) / 2.0 + (point.x - self.center.x) * self.cols_per_unit)
        row = round((self.height - 1) / 2.0 - (point.y - self.center.y) * self.rows_per_unit)
        if 0 <= column < self.width and 0 <= row < self.height:
            return int(column), int(row)
        return None


def render_scene(world: World, trails: Sequence[Sequence[Vec2]], viewport: Viewport,
                 *, ascii_only: bool = False, color: bool = False) -> list[str]:
    """Draw trails first, then bodies, on a fresh grid of exactly ``viewport.height`` lines."""
    if len(trails) != len(world.bodies):
        raise ValueError("there must be one trail per body")
    trail_char = TRAIL_ASCII if ascii_only else TRAIL_UNICODE
    grid: list[list[tuple[str, str | None]]] = [
        [(" ", None) for _ in range(viewport.width)] for _ in range(viewport.height)
    ]
    for trail in trails:
        for point in trail:
            cell = viewport.cell(point)
            if cell is not None:
                column, row = cell
                grid[row][column] = (trail_char, "gray")
    for body in world.bodies:
        cell = viewport.cell(body.pos)
        if cell is not None:
            column, row = cell
            symbol = body.symbol if len(body.symbol) == 1 else (body.symbol[:1] or "?")
            grid[row][column] = (symbol, body.color)

    lines = []
    for row in grid:
        if not color:
            lines.append("".join(char for char, _ in row))
            continue
        painted = []
        for char, color_key in row:
            if color_key is None:
                painted.append(char)
            else:
                painted.append(f"{ANSI.get(color_key, ANSI['white'])}{char}{RESET}")
        lines.append("".join(painted))
    return lines


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR sequences, for callers that need the visible width."""
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)
