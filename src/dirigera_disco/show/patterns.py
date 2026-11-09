from collections.abc import Callable

from dirigera_disco.show.color import Color

FLOW_SEGMENT_SECONDS = 2.0
JUMP_HOLD_SECONDS = 1.0
STROBE_PERIOD_SECONDS = 0.5

Pattern = Callable[[tuple[Color, ...], float], Color | None]


def flow(palette: tuple[Color, ...], t: float) -> Color | None:
    """Hold the next palette color for one segment.

    The show fades to that color over FLOW_SEGMENT_SECONDS, so the bulb does
    the blend instead of receiving every in-between hue.
    """
    if len(palette) == 1:
        return palette[0]
    index = int(t / FLOW_SEGMENT_SECONDS) % len(palette)
    return palette[(index + 1) % len(palette)]


def jump(palette: tuple[Color, ...], t: float) -> Color | None:
    """Hold a palette color, then snap to the next."""
    return palette[int(t / JUMP_HOLD_SECONDS) % len(palette)]


def strobe(palette: tuple[Color, ...], t: float) -> Color | None:
    """Alternate a palette color and dark."""
    if t % STROBE_PERIOD_SECONDS >= STROBE_PERIOD_SECONDS / 2:
        return None
    return palette[int(t / STROBE_PERIOD_SECONDS) % len(palette)]


PATTERNS: dict[str, Pattern] = {
    "flow": flow,
    "jump": jump,
    "strobe": strobe,
}
