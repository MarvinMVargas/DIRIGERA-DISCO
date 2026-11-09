import json
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_HUES = (220.0, 330.0)


@dataclass
class LightLayout:
    x: float
    y: float
    hues: tuple[float, ...]
    saturation: float
    level: int


@dataclass
class Group:
    name: str
    light_ids: list[str]
    hues: tuple[float, ...]
    saturation: float
    level: int


@dataclass
class Room:
    source_x: float = 0.5
    source_y: float = 0.12
    lights: dict[str, LightLayout] = field(default_factory=dict)
    groups: list[Group] = field(default_factory=list)
    active_group: str = "Group 1"


def _hues(item: dict) -> tuple[float, ...]:
    hues = tuple(float(hue) for hue in item.get("hues", DEFAULT_HUES))
    return hues or DEFAULT_HUES


def _saturation(item: dict) -> float:
    if "saturation" in item:
        return float(item["saturation"])
    if "sat_max" in item:
        return float(item["sat_max"])
    return 1.0


def _level(item: dict) -> int:
    return int(item.get("level", 100))


def load_room(path: Path) -> Room:
    if not path.exists():
        return Room()
    data = json.loads(path.read_text())
    source = data.get("source", {})
    lights = {
        light_id: LightLayout(
            x=float(item["x"]),
            y=float(item["y"]),
            hues=_hues(item),
            saturation=_saturation(item),
            level=_level(item),
        )
        for light_id, item in data.get("lights", {}).items()
    }
    if "groups" in data:
        groups = [
            Group(
                name=item["name"],
                light_ids=list(item.get("light_ids", [])),
                hues=_hues(item),
                saturation=_saturation(item),
                level=_level(item),
            )
            for item in data["groups"]
        ]
    else:
        members = [
            light_id
            for light_id, item in data.get("lights", {}).items()
            if item.get("in_show")
        ]
        sample = {}
        if members:
            sample = data["lights"][members[0]]
        groups = [
            Group(
                name="Group 1",
                light_ids=members,
                hues=_hues(sample),
                saturation=_saturation(sample),
                level=100,
            )
        ]
    active = data.get("active_group", groups[0].name if groups else "Group 1")
    return Room(
        source_x=float(source.get("x", 0.5)),
        source_y=float(source.get("y", 0.12)),
        lights=lights,
        groups=groups,
        active_group=active,
    )


def save_room(path: Path, room: Room) -> None:
    payload = {
        "source": {"x": room.source_x, "y": room.source_y},
        "active_group": room.active_group,
        "groups": [
            {
                "name": group.name,
                "light_ids": list(group.light_ids),
                "hues": list(group.hues),
                "saturation": group.saturation,
                "level": group.level,
            }
            for group in room.groups
        ],
        "lights": {
            light_id: {
                "x": layout.x,
                "y": layout.y,
                "hues": list(layout.hues),
                "saturation": layout.saturation,
                "level": layout.level,
            }
            for light_id, layout in room.lights.items()
        },
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
