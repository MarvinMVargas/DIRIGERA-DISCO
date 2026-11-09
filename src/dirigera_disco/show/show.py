import sys
import time
from concurrent.futures import ThreadPoolExecutor

from dirigera.devices.light import Light

from dirigera_disco.device.lights import supports_color
from dirigera_disco.show.color import Color
from dirigera_disco.show.patterns import JUMP_HOLD_SECONDS, Pattern

FRAME_SECONDS = 1 / 8


def _remember(light: Light, attributes: dict) -> None:
    if "isOn" in attributes:
        light.attributes.is_on = attributes["isOn"]
    if "lightLevel" in attributes:
        light.attributes.light_level = attributes["lightLevel"]
    if "colorHue" in attributes:
        light.attributes.color_hue = attributes["colorHue"]
        light.attributes.color_saturation = attributes["colorSaturation"]
        light.attributes.color_mode = "color"


def _send(light: Light, attributes: dict, transition_ms: int) -> None:
    light.dirigera_client.patch(
        route=f"/devices/{light.id}",
        data=[{"attributes": attributes, "transitionTime": transition_ms}],
    )
    _remember(light, attributes)


def _send_steps(light: Light, steps: list[tuple[dict, int]]) -> None:
    # Brightness and hue must be separate patches. The hub drops lightLevel
    # when it arrives in the same request as colorHue.
    for attributes, transition_ms in steps:
        _send(light, attributes, transition_ms)


def _apply(
    pool: ThreadPoolExecutor,
    jobs: list[tuple[Light, list[tuple[dict, int]]]],
) -> None:
    """Patch every light at once. One light stays on the calling thread."""
    if len(jobs) <= 1:
        for light, steps in jobs:
            _send_steps(light, steps)
        return
    futures = [pool.submit(_send_steps, light, steps) for light, steps in jobs]
    for future in futures:
        future.result()


def run_show(
    lights: list[Light],
    palette: tuple[Color, ...],
    pattern: Pattern,
    seconds: float,
    transition_ms: int = 0,
) -> None:
    """Apply one pattern to every color-capable light until seconds elapse.

    Patches for the same step are sent together. transition_ms is how long each
    bulb takes to fade into that step. Ctrl-C leaves the lights on their last update.
    """
    active: list[Light] = []
    for light in lights:
        name = light.attributes.custom_name
        if not light.is_reachable:
            print(f"Skipping {name}: not reachable", file=sys.stderr)
        elif not supports_color(light):
            print(f"Skipping {name}: does not accept color", file=sys.stderr)
        else:
            active.append(light)
    if not active:
        return

    last: Color | None = None
    seen = False
    started = time.monotonic()
    next_frame = started
    with ThreadPoolExecutor(max_workers=len(active)) as pool:
        _apply(pool, [(light, [({"isOn": True}, 0)]) for light in active])
        try:
            while True:
                elapsed = time.monotonic() - started
                if elapsed >= seconds:
                    break
                target = pattern(palette, elapsed)
                if not seen or target != last:
                    if target is None:
                        steps = [({"lightLevel": 1}, 0)]
                    else:
                        steps = []
                        if not seen or last is None:
                            steps.append(({"lightLevel": 100}, 0))
                        steps.append(
                            (
                                {
                                    "colorHue": target.hue,
                                    "colorSaturation": target.saturation,
                                },
                                transition_ms,
                            )
                        )
                    _apply(pool, [(light, steps) for light in active])
                    last = target
                    seen = True
                next_frame += FRAME_SECONDS
                delay = next_frame - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                else:
                    next_frame = time.monotonic()
        except KeyboardInterrupt:
            return


def run_live(
    assignments: list[tuple[Light, tuple[Color, ...], int | None]],
    pattern: Pattern,
    transition_ms: int,
    stop,
    step=None,
) -> None:
    """Run until stop is set. Each light uses its own palette on the same clock.

    step(), when given, is how many musical hits have happened. Jump then snaps
    once per hit instead of on a timer. A fixed level stays on the bulb while the
    color changes. A strobe uses that level on the bright step and level 1 on the
    dark step. Ctrl-C leaves the last update.
    """
    active = [
        (light, palette, level) for light, palette, level in assignments if palette
    ]
    if not active:
        return
    last: dict[str, Color | None] = {light.id: None for light, _, _ in active}
    seen: dict[str, bool] = {light.id: False for light, _, _ in active}
    levels: dict[str, int] = {}
    started = time.monotonic()
    next_frame = started
    with ThreadPoolExecutor(max_workers=len(active)) as pool:
        _apply(pool, [(light, [({"isOn": True}, 0)]) for light, _, _ in active])
        try:
            while not stop.is_set():
                elapsed = time.monotonic() - started
                clock = elapsed if step is None else step() * JUMP_HOLD_SECONDS
                jobs: list[tuple[Light, list[tuple[dict, int]]]] = []
                for light, palette, level in active:
                    target = pattern(palette, clock)
                    bright = 100 if level is None else level
                    steps: list[tuple[dict, int]] = []
                    if not seen[light.id] or target != last[light.id]:
                        wanted = 1 if target is None else bright
                        if levels.get(light.id) != wanted:
                            steps.append(({"lightLevel": wanted}, 0))
                            levels[light.id] = wanted
                        if target is not None:
                            steps.append(
                                (
                                    {
                                        "colorHue": target.hue,
                                        "colorSaturation": target.saturation,
                                    },
                                    transition_ms,
                                )
                            )
                        last[light.id] = target
                        seen[light.id] = True
                    if steps:
                        jobs.append((light, steps))
                if jobs:
                    _apply(pool, jobs)
                next_frame += FRAME_SECONDS
                delay = next_frame - time.monotonic()
                if delay > 0:
                    stop.wait(delay)
                else:
                    next_frame = time.monotonic()
        except KeyboardInterrupt:
            return
