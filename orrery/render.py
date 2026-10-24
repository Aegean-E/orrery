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
TRAIL_ANSI = {
    "trail_yellow": "\x1b[2;33m",
    "trail_gold": "\x1b[2;33m",
    "trail_gray": "\x1b[2;90m",
    "trail_blue": "\x1b[2;34m",
    "trail_red": "\x1b[2;31m",
    "trail_orange": "\x1b[2;38;5;208m",
    "trail_cyan": "\x1b[2;36m",
    "trail_magenta": "\x1b[2;35m",
    "trail_green": "\x1b[2;32m",
    "trail_white": "\x1b[2;37m",
}
TRAIL_UNICODE = "·"
TRAIL_ASCII = "."
CELL_ASPECT = 2.0
BRAILLE_BITS = (
    (0x01, 0x08),
    (0x02, 0x10),
    (0x04, 0x20),
    (0x40, 0x80),
)


@dataclass(frozen=True, slots=True)
class Viewport:
    """A rectangular map from world units to terminal cells."""

    width: int
    height: int
    span: float
    center: Vec2 = Vec2()
    aspect: float = CELL_ASPECT

    def __post_init__(self) -> None:
        if self.width < 5 or self.height < 3:
            raise ValueError("the viewport needs at least 5 columns and 3 rows")
        if not math.isfinite(self.span) or self.span <= 0.0:
            raise ValueError("the viewport span must be a positive finite number")
        if not (math.isfinite(self.center.x) and math.isfinite(self.center.y)):
            raise ValueError("the viewport centre must be finite")
        if not math.isfinite(self.aspect) or self.aspect <= 0.0:
            raise ValueError("the viewport aspect must be a positive finite number")

    @property
    def rows_per_unit(self) -> float:
        return (self.height - 1) / self.span

    @property
    def cols_per_unit(self) -> float:
        return self.aspect * self.rows_per_unit

    def cell(self, point: Vec2) -> tuple[int, int] | None:
        """Return ``(column, row)`` for a world point, or ``None`` when off-screen."""
        column = round((self.width - 1) / 2.0 + (point.x - self.center.x) * self.cols_per_unit)
        row = round((self.height - 1) / 2.0 - (point.y - self.center.y) * self.rows_per_unit)
        if 0 <= column < self.width and 0 <= row < self.height:
            return int(column), int(row)
        return None

    def subcell(self, point: Vec2) -> tuple[int, int] | None:
        """Return ``(subcolumn, subrow)`` in the 2x4 Braille grid, or ``None``."""
        sub_width = self.width * 2
        sub_height = self.height * 4
        column = round(
            (sub_width - 1) / 2.0
            + (point.x - self.center.x) * 2.0 * self.cols_per_unit
        )
        row = round(
            (sub_height - 1) / 2.0
            - (point.y - self.center.y) * 4.0 * self.rows_per_unit
        )
        if 0 <= column < sub_width and 0 <= row < sub_height:
            return int(column), int(row)
        return None


def _line_cells(start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
    """Bresenham line in cell coordinates, including both endpoints."""
    x0, y0 = start
    x1, y1 = end
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    error = dx + dy
    cells = []
    while True:
        cells.append((x0, y0))
        if x0 == x1 and y0 == y1:
            return cells
        doubled = 2 * error
        if doubled >= dy:
            error += dy
            x0 += sx
        if doubled <= dx:
            error += dx
            y0 += sy


def _trail_color(color_key: str) -> str:
    return f"trail_{color_key}"


def _paint_grid(grid: list[list[tuple[str, str | None]]], color: bool) -> list[str]:
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
                code = TRAIL_ANSI.get(color_key, ANSI.get(color_key, ANSI["white"]))
                painted.append(f"{code}{char}{RESET}")
        lines.append("".join(painted))
    return lines


def _set_braille(bits: list[list[int]], colors: list[list[str | None]],
                 subcell: tuple[int, int], color_key: str) -> None:
    sub_column, sub_row = subcell
    column = sub_column // 2
    row = sub_row // 4
    bits[row][column] |= BRAILLE_BITS[sub_row % 4][sub_column % 2]
    colors[row][column] = color_key


def _render_braille(world: World, trails: Sequence[Sequence[Vec2]], viewport: Viewport,
                    color: bool) -> list[str]:
    bits = [[0 for _ in range(viewport.width)] for _ in range(viewport.height)]
    trail_colors: list[list[str | None]] = [
        [None for _ in range(viewport.width)] for _ in range(viewport.height)
    ]
    for body, trail in zip(world.bodies, trails):
        color_key = _trail_color(body.color)
        previous = None
        for point in trail:
            current = viewport.subcell(point)
            if current is not None:
                if previous is None:
                    _set_braille(bits, trail_colors, current, color_key)
                else:
                    for subcell in _line_cells(previous, current):
                        _set_braille(bits, trail_colors, subcell, color_key)
            previous = current

    grid: list[list[tuple[str, str | None]]] = [
        [(" ", None) for _ in range(viewport.width)] for _ in range(viewport.height)
    ]
    for row in range(viewport.height):
        for column in range(viewport.width):
            mask = bits[row][column]
            if mask:
                grid[row][column] = (
                    chr(0x2800 + mask),
                    trail_colors[row][column] or "trail_gray",
                )
    for body in world.bodies:
        cell = viewport.cell(body.pos)
        if cell is not None:
            column, row = cell
            symbol = body.symbol if len(body.symbol) == 1 else (body.symbol[:1] or "?")
            grid[row][column] = (symbol, body.color)
    return _paint_grid(grid, color)


def render_scene(world: World, trails: Sequence[Sequence[Vec2]], viewport: Viewport,
                 *, ascii_only: bool = False, color: bool = False,
                 braille: bool = False) -> list[str]:
    """Draw trails first, then bodies, on a fresh grid of exactly ``viewport.height`` lines."""
    if len(trails) != len(world.bodies):
        raise ValueError("there must be one trail per body")
    if braille:
        return _render_braille(world, trails, viewport, color)
    trail_char = TRAIL_ASCII if ascii_only else TRAIL_UNICODE
    grid: list[list[tuple[str, str | None]]] = [
        [(" ", None) for _ in range(viewport.width)] for _ in range(viewport.height)
    ]
    for body, trail in zip(world.bodies, trails):
        color_key = _trail_color(body.color)
        previous = None
        for point in trail:
            cell = viewport.cell(point)
            if cell is not None:
                if previous is None:
                    column, row = cell
                    grid[row][column] = (trail_char, color_key)
                else:
                    for column, row in _line_cells(previous, cell):
                        grid[row][column] = (trail_char, color_key)
            previous = cell
    for body in world.bodies:
        cell = viewport.cell(body.pos)
        if cell is not None:
            column, row = cell
            symbol = body.symbol if len(body.symbol) == 1 else (body.symbol[:1] or "?")
            grid[row][column] = (symbol, body.color)
    return _paint_grid(grid, color)


def strip_ansi(text: str) -> str:
    """Remove ANSI SGR sequences, for callers that need the visible width."""
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)
