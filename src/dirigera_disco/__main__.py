import argparse
import sys

from dirigera.devices.light import Light

from dirigera_disco.device.hub import connect
from dirigera_disco.device.lights import describe, set_color, set_power
from dirigera_disco.show.color import PALETTES, Color
from dirigera_disco.show.patterns import FLOW_SEGMENT_SECONDS, PATTERNS, flow
from dirigera_disco.show.show import run_show


def select_lights(lights: list[Light], names: list[str]) -> list[Light]:
    """Reachable lights, or the named ones when names is not empty."""
    if not names:
        return [light for light in lights if light.is_reachable]

    by_name: dict[str, list[Light]] = {}
    for light in lights:
        by_name.setdefault(light.attributes.custom_name, []).append(light)

    missing = [name for name in names if name not in by_name]
    if missing:
        raise ValueError("No light named " + ", ".join(missing))

    chosen: list[Light] = []
    seen: set[str] = set()
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        for light in by_name[name]:
            if light.is_reachable:
                chosen.append(light)
            else:
                print(f"Skipping {name}: not reachable", file=sys.stderr)
    return chosen


def _add_name_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--name",
        action="append",
        default=[],
        help="Light name. Repeat for several. Omit for every reachable light.",
    )


def main() -> None:
    parser = argparse.ArgumentParser(prog="dirigera-disco")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="List lights on the hub")
    sub.add_parser("gui", help="Open the show window")
    _add_name_argument(sub.add_parser("on", help="Turn lights on"))
    _add_name_argument(sub.add_parser("off", help="Turn lights off"))
    color_parser = sub.add_parser("color", help="Set light hue and saturation")
    _add_name_argument(color_parser)
    color_parser.add_argument("--hue", type=float, required=True)
    color_parser.add_argument("--saturation", type=float, required=True)
    cycle_parser = sub.add_parser("cycle", help="Run a color pattern for a few seconds")
    _add_name_argument(cycle_parser)
    cycle_parser.add_argument("--pattern", required=True, choices=sorted(PATTERNS))
    cycle_parser.add_argument("--palette", required=True, choices=sorted(PALETTES))
    cycle_parser.add_argument("--seconds", type=float, required=True)
    args = parser.parse_args()

    try:
        hub = connect()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error

    if args.command == "list":
        for light in hub.get_lights():
            print(describe(light))
        return

    if args.command == "gui":
        from dirigera_disco.gui.gui import Gui

        Gui(hub).run()
        return

    try:
        lights = select_lights(hub.get_lights(), args.name)
    except ValueError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1) from error

    if args.command == "color":
        try:
            color = Color(hue=args.hue, saturation=args.saturation)
        except ValueError as error:
            print(error, file=sys.stderr)
            raise SystemExit(1) from error
        for light in lights:
            name = light.attributes.custom_name
            if set_color(light, color):
                print(f"{name} hue={color.hue} saturation={color.saturation}")
            else:
                print(f"Skipping {name}: does not accept color", file=sys.stderr)
        return

    if args.command == "cycle":
        if args.seconds <= 0:
            print("seconds must be positive", file=sys.stderr)
            raise SystemExit(1)
        names = ", ".join(light.attributes.custom_name for light in lights)
        print(f"{args.pattern} {args.palette} for {args.seconds}s on {names}")
        pattern = PATTERNS[args.pattern]
        transition_ms = round(FLOW_SEGMENT_SECONDS * 1000) if pattern is flow else 0
        run_show(
            lights,
            PALETTES[args.palette],
            pattern,
            args.seconds,
            transition_ms,
        )
        return

    turn_on = args.command == "on"
    for light in lights:
        set_power(light, turn_on)
        print(f"{light.attributes.custom_name} {'on' if turn_on else 'off'}")


if __name__ == "__main__":
    main()
