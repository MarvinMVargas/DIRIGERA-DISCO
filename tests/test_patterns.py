from dirigera_disco.show.color import Color, blend
from dirigera_disco.show.patterns import (
    FLOW_SEGMENT_SECONDS,
    JUMP_HOLD_SECONDS,
    STROBE_PERIOD_SECONDS,
    flow,
    jump,
    strobe,
)


def test_blend_wraps_hue_the_short_way() -> None:
    mixed = blend(Color(350, 1), Color(10, 0), 0.5)
    assert mixed.hue == 0
    assert mixed.saturation == 0.5


def test_blend_ends() -> None:
    start = Color(20, 0.2)
    end = Color(80, 0.8)
    assert blend(start, end, 0) == start
    assert blend(start, end, 1) == end


def test_flow_holds_the_next_palette_color() -> None:
    palette = (Color(350, 1), Color(10, 0), Color(120, 1))
    assert flow(palette, 0) == palette[1]
    assert flow(palette, FLOW_SEGMENT_SECONDS / 2) == palette[1]
    assert flow(palette, FLOW_SEGMENT_SECONDS) == palette[2]


def test_jump_holds_then_snaps() -> None:
    palette = (Color(0, 1), Color(120, 1))
    assert jump(palette, 0) == palette[0]
    assert jump(palette, JUMP_HOLD_SECONDS - 0.01) == palette[0]
    assert jump(palette, JUMP_HOLD_SECONDS) == palette[1]


def test_strobe_alternates_color_and_dark() -> None:
    palette = (Color(0, 1), Color(120, 1))
    assert strobe(palette, 0) == palette[0]
    assert strobe(palette, STROBE_PERIOD_SECONDS / 2) is None
    assert strobe(palette, STROBE_PERIOD_SECONDS) == palette[1]
