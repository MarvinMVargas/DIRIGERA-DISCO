import json
from pathlib import Path

from dirigera_disco.gui.room import Group, LightLayout, Room, load_room, save_room
from dirigera_disco.show.audio import BEAT_COOLDOWN_SECONDS, brightness_for, is_beat
from dirigera_disco.show.color import PRESETS, colors_for, hue_at, hue_in_range, hue_position, hue_ranges
from dirigera_disco.show.patterns import FLOW_SEGMENT_SECONDS, flow


def test_flow_stops_share_one_saturation() -> None:
    palette = colors_for((0, 40, 80), 0.6)
    for step in range(3):
        color = flow(palette, step * FLOW_SEGMENT_SECONDS)
        assert color is not None
        assert color.saturation == 0.6


def test_two_presets_differ_at_the_same_time() -> None:
    blue = colors_for(PRESETS["Blue and pink"], 1)
    green = colors_for(PRESETS["Green and purple"], 1)
    assert flow(blue, 0) != flow(green, 0)
    for color in blue + green:
        assert color.saturation == 1


def test_hue_stops_form_ranges() -> None:
    assert hue_ranges((220.0, 330.0)) == ((220.0, 330.0),)
    assert hue_ranges((0.0, 35.0, 220.0, 245.0)) == ((0.0, 35.0), (220.0, 245.0))
    assert hue_ranges((40.0,)) == ((40.0, 40.0),)
    assert hue_in_range(10, 350, 20)
    assert not hue_in_range(180, 350, 20)
    assert hue_position(360, 400) == 400


def test_hue_handle_maps_back_to_degrees() -> None:
    assert hue_at(0, 360) == 0
    assert hue_at(180, 360) == 180
    assert hue_at(360, 360) == 360
    assert hue_position(90, 360) == 90
    assert hue_at(hue_position(240, 400), 400) == 240


def test_room_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "room.json"
    room = Room(
        source_x=0.2,
        source_y=0.3,
        lights={
            "lamp": LightLayout(
                x=0.4,
                y=0.6,
                hues=(10.0, 40.0),
                saturation=0.9,
                level=70,
            )
        },
        groups=[
            Group("Group 2", ["lamp"], (10.0, 40.0), 0.9, 70),
        ],
        active_group="Group 2",
    )
    save_room(path, room)
    loaded = load_room(path)
    assert loaded.source_x == 0.2
    assert loaded.active_group == "Group 2"
    assert loaded.groups[0].light_ids == ["lamp"]
    assert loaded.groups[0].saturation == 0.9
    assert loaded.groups[0].level == 70
    assert loaded.lights["lamp"].hues == (10.0, 40.0)


def test_old_room_becomes_one_group(tmp_path: Path) -> None:
    path = tmp_path / "room.json"
    path.write_text(
        json.dumps(
            {
                "source": {"x": 0.5, "y": 0.1},
                "lights": {
                    "a": {
                        "x": 0.2,
                        "y": 0.3,
                        "hues": [10, 20],
                        "sat_min": 0.2,
                        "sat_max": 0.8,
                        "in_show": True,
                    },
                    "b": {
                        "x": 0.4,
                        "y": 0.5,
                        "hues": [1, 2],
                        "sat_min": 0.4,
                        "sat_max": 1,
                        "in_show": False,
                    },
                },
            }
        )
    )
    room = load_room(path)
    assert room.groups[0].name == "Group 1"
    assert room.groups[0].light_ids == ["a"]
    assert room.groups[0].saturation == 0.8
    assert room.groups[0].hues == (10.0, 20.0)
    assert room.lights["a"].saturation == 0.8
    assert room.lights["b"].saturation == 1


def test_brightness_stays_in_range() -> None:
    assert brightness_for(0) == 15
    assert brightness_for(1) == 100
    assert 15 <= brightness_for(0.05) <= 100


def test_beat_needs_a_rise_and_then_waits() -> None:
    assert is_beat(0.05, 0.01, 0.02, BEAT_COOLDOWN_SECONDS)
    assert not is_beat(0.05, 0.048, 0.02, BEAT_COOLDOWN_SECONDS)
    assert not is_beat(0.05, 0.01, 0.02, 0.05)
