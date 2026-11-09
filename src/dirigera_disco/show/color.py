from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    hue: float
    saturation: float

    def __post_init__(self) -> None:
        if self.hue < 0 or self.hue > 360:
            raise ValueError("hue must be between 0 and 360")
        if self.saturation < 0 or self.saturation > 1:
            raise ValueError("saturation must be between 0 and 1")


PRESETS: dict[str, tuple[float, ...]] = {
    "Blue and pink": (220.0, 330.0),
    "Green and purple": (130.0, 280.0),
    "Red, orange, blue, and yellow": (0.0, 35.0, 48.0, 65.0, 220.0, 245.0),
}


def colors_for(hues: tuple[float, ...], saturation: float) -> tuple[Color, ...]:
    """Build a palette. Every stop uses the same saturation."""
    sat = min(1.0, max(0.0, saturation))
    return tuple(Color(hue % 360, sat) for hue in hues)


def hue_at(x: float, width: float) -> float:
    """Map a slider position to a hue from 0 to 360."""
    if width <= 0:
        return 0.0
    return round(min(360.0, max(0.0, x / width * 360)), 2)


def hue_position(hue: float, width: float) -> float:
    """Map a hue back onto a slider of the given width."""
    return min(360.0, max(0.0, hue)) / 360 * width


def hue_ranges(hues: tuple[float, ...]) -> tuple[tuple[float, float], ...]:
    """Pair hue stops into ranges. A leftover stop is a single color."""
    if not hues:
        return ((0.0, 0.0),)
    pairs: list[tuple[float, float]] = []
    index = 0
    while index + 1 < len(hues):
        pairs.append((hues[index], hues[index + 1]))
        index += 2
    if index < len(hues):
        pairs.append((hues[index], hues[index]))
    return tuple(pairs)


def hue_in_range(hue: float, start: float, end: float) -> bool:
    """True when hue sits inside the arc from start to end, wrapping past 360."""
    hue %= 360
    start %= 360
    end %= 360
    if start <= end:
        return start <= hue <= end
    return hue >= start or hue <= end


PALETTES: dict[str, tuple[Color, ...]] = {
    "rainbow": (
        Color(0, 1),
        Color(60, 1),
        Color(120, 1),
        Color(180, 1),
        Color(240, 1),
        Color(300, 1),
    ),
    "warm": (Color(15, 0.9), Color(40, 0.8), Color(0, 1)),
    "cool": (Color(190, 0.8), Color(220, 1), Color(260, 0.7)),
    "party": (Color(320, 1), Color(280, 1), Color(40, 1), Color(140, 1)),
}


def blend(start: Color, end: Color, t: float) -> Color:
    """Interpolate saturation linearly and hue the short way around the circle."""
    if t < 0:
        t = 0
    elif t > 1:
        t = 1
    delta = (end.hue - start.hue + 180) % 360 - 180
    hue = (start.hue + delta * t) % 360
    saturation = start.saturation + (end.saturation - start.saturation) * t
    return Color(hue, saturation)
