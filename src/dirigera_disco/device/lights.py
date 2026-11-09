from dirigera.devices.light import Light

from dirigera_disco.show.color import Color


def supports_color(light: Light) -> bool:
    return "colorHue" in light.capabilities.can_receive


def set_power(light: Light, on: bool) -> None:
    light.set_light(lamp_on=on)


def set_level(light: Light, level: int) -> None:
    light.set_light_level(light_level=level)


def set_color(light: Light, color: Color) -> bool:
    """Apply a hue. Return False when the bulb cannot show one."""
    if not supports_color(light):
        return False
    light.set_light_color(hue=color.hue, saturation=color.saturation)
    return True


def describe(light: Light) -> str:
    power = "on" if light.attributes.is_on else "off"
    reachable = "yes" if light.is_reachable else "no"
    color = "yes" if supports_color(light) else "no"
    return (
        f"{light.attributes.custom_name}"
        f"  id={light.id}"
        f"  reachable={reachable}"
        f"  power={power}"
        f"  color={color}"
    )
