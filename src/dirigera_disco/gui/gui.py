import colorsys
import queue
import threading
from pathlib import Path

import pygame
from dirigera.devices.light import Light

from dirigera_disco.device.lights import set_color, set_level, set_power, supports_color
from dirigera_disco.gui.room import DEFAULT_HUES, Group, LightLayout, Room, load_room, save_room
from dirigera_disco.show.audio import MicLevel
from dirigera_disco.show.color import (
    PRESETS,
    Color,
    colors_for,
    hue_at,
    hue_in_range,
    hue_position,
    hue_ranges,
)
from dirigera_disco.show.patterns import FLOW_SEGMENT_SECONDS, PATTERNS, flow
from dirigera_disco.show.show import run_live

ROOM_FILE = Path("room.json")
PATTERN_NAMES = tuple(PATTERNS)
WIDTH = 1120
HEIGHT = 880

BG = (18, 16, 32)
PANEL = (30, 28, 50)
BUTTON = (58, 54, 86)
PRIMARY = (108, 92, 214)
TEXT = (240, 238, 248)
MUTED = (176, 170, 198)
ROW = (36, 34, 58)
ROW_ON = (58, 54, 92)


class Gui:
    def __init__(self, hub) -> None:
        self.hub = hub
        self.lights: list[Light] = list(hub.get_lights())
        self.room: Room = load_room(ROOM_FILE)
        self._ensure_layouts()
        self.selected_id = self.lights[0].id if self.lights else None
        self.pattern_name = "flow"
        self.status = "Add lights to a group, set the sliders, then Apply or Start."
        self.running = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._messages: queue.Queue[str] = queue.Queue()
        self._drag: str | None = None
        self._buttons: list[tuple[pygame.Rect, callable]] = []
        self._hue_rect = pygame.Rect(0, 0, 0, 0)
        self._level_rect = pygame.Rect(0, 0, 0, 0)
        self.title_font: pygame.font.Font
        self.section_font: pygame.font.Font
        self.font: pygame.font.Font

    def run(self) -> None:
        pygame.init()
        self.title_font = _font(34, bold=True)
        self.section_font = _font(20, bold=True)
        self.font = _font(16, bold=False)
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption("DIRIGERADisco")
        clock = pygame.time.Clock()
        try:
            while True:
                self._poll()
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        self._stop_show()
                        return
                    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._mouse_down(event.pos)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                        if self._remove_hue_range(event.pos):
                            self._save()
                    elif event.type == pygame.MOUSEMOTION and self._drag:
                        self._mouse_drag(event.pos)
                    elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
                        self._drag = None
                        self._save()
                self._draw(screen)
                pygame.display.flip()
                clock.tick(30)
        finally:
            self._stop_show()
            pygame.quit()

    def _ensure_layouts(self) -> None:
        known = {light.id for light in self.lights}
        for index, light in enumerate(self.lights):
            if light.id not in self.room.lights:
                self.room.lights[light.id] = LightLayout(
                    x=0.18 + (index % 4) * 0.2,
                    y=0.28 + (index // 4) * 0.28,
                    hues=DEFAULT_HUES,
                    saturation=1.0,
                    level=100,
                )
        if not self.room.groups:
            members = [light.id for light in self.lights if supports_color(light)]
            self.room.groups.append(
                Group("Group 1", members, DEFAULT_HUES, 1.0, 100)
            )
            self.room.active_group = "Group 1"
        for group in self.room.groups:
            group.light_ids = [light_id for light_id in group.light_ids if light_id in known]
        names = {group.name for group in self.room.groups}
        if self.room.active_group not in names:
            self.room.active_group = self.room.groups[0].name

    def _group(self) -> Group:
        for group in self.room.groups:
            if group.name == self.room.active_group:
                return group
        self.room.active_group = self.room.groups[0].name
        return self.room.groups[0]

    def _in_any_group(self, light_id: str) -> bool:
        return self._settings_for(light_id) is not None

    def _settings_for(self, light_id: str) -> Group | None:
        active = self._group()
        if light_id in active.light_ids:
            return active
        for group in self.room.groups:
            if light_id in group.light_ids:
                return group
        return None

    def _save(self) -> None:
        save_room(ROOM_FILE, self.room)

    def _poll(self) -> None:
        while True:
            try:
                self.status = self._messages.get_nowait()
            except queue.Empty:
                break
        if self.running and self._thread is not None and not self._thread.is_alive():
            self.running = False

    def _mouse_down(self, pos) -> None:
        for rect, action in reversed(self._buttons):
            if rect.collidepoint(pos):
                action()
                self._save()
                return
        if self._hit_slider(pos):
            return
        self._hit_room(pos)

    def _hit_slider(self, pos) -> bool:
        if self._hue_rect.collidepoint(pos):
            index = self._nearest_hue_handle(pos[0])
            if index is None:
                self._add_hue_range(hue_at(pos[0] - self._hue_rect.x, self._hue_rect.w))
                self._save()
                return True
            self._drag = f"hue:{index}"
            self._set_hue_from_x(pos[0])
            return True
        if self._level_rect.collidepoint(pos):
            self._drag = "level"
            self._set_level_from_x(pos[0])
            return True
        return False

    def _hue_stops(self) -> list[float]:
        return [hue for start, end in hue_ranges(self._group().hues) for hue in (start, end)]

    def _nearest_hue_handle(self, x: float) -> int | None:
        nearest = None
        nearest_distance = 14
        for index, hue in enumerate(self._hue_stops()):
            handle = self._hue_rect.x + hue_position(hue, self._hue_rect.w)
            distance = abs(x - handle)
            if distance <= nearest_distance:
                nearest = index
                nearest_distance = distance
        return nearest

    def _set_hue_from_x(self, x: float) -> None:
        if not isinstance(self._drag, str) or not self._drag.startswith("hue:"):
            return
        index = int(self._drag.removeprefix("hue:"))
        stops = self._hue_stops()
        if index >= len(stops):
            return
        stops[index] = hue_at(x - self._hue_rect.x, self._hue_rect.w)
        self._group().hues = tuple(stops)

    def _add_hue_range(self, hue: float) -> None:
        stops = self._hue_stops()
        if len(stops) >= 16:
            self.status = "Eight hue ranges is the maximum"
            return
        start = round(max(0.0, hue - 12), 2)
        end = round(min(360.0, hue + 12), 2)
        if end - start < 8:
            if hue < 180:
                start, end = 0.0, 24.0
            else:
                start, end = 336.0, 360.0
        stops.extend((start, end))
        self._group().hues = tuple(stops)
        self.status = "Added a hue range"

    def _remove_hue_range(self, pos) -> bool:
        if not self._hue_rect.collidepoint(pos):
            return False
        stops = self._hue_stops()
        if len(stops) <= 2:
            self.status = "Keep at least one hue range"
            return True
        index = self._nearest_hue_handle(pos[0])
        if index is None:
            hue = hue_at(pos[0] - self._hue_rect.x, self._hue_rect.w)
            ranges = hue_ranges(tuple(stops))
            matches = [
                range_index
                for range_index, (start, end) in enumerate(ranges)
                if hue_in_range(hue, start, end)
            ]
            if not matches:
                return True
            index = matches[0] * 2
        del stops[index - index % 2 : index - index % 2 + 2]
        self._group().hues = tuple(stops)
        self.status = "Removed a hue range"
        return True

    def _set_level_from_x(self, x: float) -> None:
        span = self._level_rect.w or 1
        ratio = min(1.0, max(0.0, (x - self._level_rect.x) / span))
        self._group().level = int(round(1 + ratio * 99))

    def _mouse_drag(self, pos) -> None:
        if isinstance(self._drag, str) and self._drag.startswith("hue:"):
            self._set_hue_from_x(pos[0])
            return
        if self._drag == "level":
            self._set_level_from_x(pos[0])
            return
        rect = self._room_rect()
        x = min(1.0, max(0.0, (pos[0] - rect.x) / rect.w))
        y = min(1.0, max(0.0, (pos[1] - rect.y) / rect.h))
        if self._drag == "source":
            self.room.source_x = x
            self.room.source_y = y
            return
        layout = self.room.lights.get(self._drag or "")
        if layout is not None:
            layout.x = x
            layout.y = y

    def _hit_room(self, pos) -> bool:
        rect = self._room_rect()
        if not rect.collidepoint(pos):
            return False
        source = self._room_point(self.room.source_x, self.room.source_y)
        if _near(pos, source):
            self._drag = "source"
            return True
        for light in reversed(self.lights):
            if not self._in_any_group(light.id):
                continue
            layout = self.room.lights[light.id]
            if _near(pos, self._room_point(layout.x, layout.y)):
                self._drag = light.id
                self.selected_id = light.id
                return True
        return True

    def _toggle_member(self, light: Light) -> None:
        if not supports_color(light):
            self.status = f"{light.attributes.custom_name} cannot show a color"
            return
        group = self._group()
        if light.id in group.light_ids:
            group.light_ids.remove(light.id)
        else:
            group.light_ids.append(light.id)
        self.selected_id = light.id

    def _choose(self, light: Light) -> None:
        self.selected_id = light.id

    def _power(self, light: Light, on: bool) -> None:
        if self.running:
            self.status = "Stop the show before switching a light on or off"
            return
        if not light.is_reachable:
            self.status = f"{light.attributes.custom_name} is not reachable"
            return

        def send() -> None:
            try:
                set_power(light, on)
                self._messages.put(f"{light.attributes.custom_name} {'on' if on else 'off'}")
            except Exception as error:
                self._messages.put(str(error))

        threading.Thread(target=send, daemon=True).start()

    def _cycle_pattern(self) -> None:
        if self.running:
            self.status = "Stop the show before changing the pattern"
            return
        index = PATTERN_NAMES.index(self.pattern_name)
        self.pattern_name = PATTERN_NAMES[(index + 1) % len(PATTERN_NAMES)]

    def _cycle_group(self) -> None:
        names = [group.name for group in self.room.groups]
        index = names.index(self._group().name)
        self.room.active_group = names[(index + 1) % len(names)]

    def _new_group(self) -> None:
        names = {group.name for group in self.room.groups}
        number = 1
        while f"Group {number}" in names:
            number += 1
        current = self._group()
        group = Group(
            f"Group {number}",
            [],
            current.hues,
            current.saturation,
            current.level,
        )
        self.room.groups.append(group)
        self.room.active_group = group.name
        self.status = f"Editing {group.name}"

    def _delete_group(self) -> None:
        if len(self.room.groups) == 1:
            self.status = "Keep at least one group"
            return
        name = self._group().name
        self.room.groups = [group for group in self.room.groups if group.name != name]
        self.room.active_group = self.room.groups[0].name
        self.status = f"Deleted {name}"

    def _set_hues(self, hues: tuple[float, ...]) -> None:
        self._group().hues = hues

    def _apply_group(self) -> None:
        if self.running:
            self.status = "Stop the show before applying a color"
            return
        group = self._group()
        targets = [
            light
            for light in self.lights
            if light.id in group.light_ids and light.is_reachable and supports_color(light)
        ]
        if not targets:
            self.status = "Add a reachable color light to this group"
            return
        hue = group.hues[0] % 360
        level = min(100, max(1, group.level))
        for light in targets:
            layout = self.room.lights[light.id]
            layout.hues = group.hues
            layout.saturation = 1.0
            layout.level = level
        self._save()

        def send() -> None:
            try:
                color = Color(hue, 1.0)
                for light in targets:
                    if set_color(light, color):
                        set_level(light, level)
                self._messages.put(f"Applied {group.name}")
            except Exception as error:
                self._messages.put(str(error))

        threading.Thread(target=send, daemon=True).start()

    def _start_show(self) -> None:
        if self.running:
            return
        pattern = PATTERNS[self.pattern_name]
        assignments = []
        for light in self.lights:
            group = self._settings_for(light.id)
            if group is None or not light.is_reachable or not supports_color(light):
                continue
            fixed = min(100, max(1, group.level))
            assignments.append((light, colors_for(group.hues, 1.0), fixed))
        if not assignments:
            self.status = "Add at least one reachable color light to a group"
            return
        transition_ms = round(FLOW_SEGMENT_SECONDS * 1000) if pattern is flow else 0
        self._stop.clear()
        self.running = True
        self.status = f"Playing {self.pattern_name}"

        def work() -> None:
            mic = None
            try:
                step = None
                if self.pattern_name == "jump":
                    mic = MicLevel()
                    mic.start()
                    step = mic.beats
                run_live(assignments, pattern, transition_ms, self._stop, step)
            except Exception as error:
                self._messages.put(str(error))
            else:
                self._messages.put("Show stopped")
            finally:
                if mic is not None:
                    mic.stop()

        self._thread = threading.Thread(target=work, daemon=True)
        self._thread.start()

    def _stop_show(self) -> None:
        self._stop.set()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
        self.running = False

    def _draw(self, screen: pygame.Surface) -> None:
        self._buttons = []
        screen.fill(BG)
        screen.blit(self.title_font.render("DIRIGERADisco", True, TEXT), (24, 18))
        self._draw_list(screen)
        self._draw_controls(screen)
        self._draw_room(screen)
        screen.blit(self.font.render(self.status, True, MUTED), (24, HEIGHT - 36))

    def _draw_list(self, screen) -> None:
        screen.blit(self.section_font.render("Lights", True, TEXT), (24, 72))
        group = self._group()
        for index, light in enumerate(self.lights):
            y = 108 + index * 42
            row = pygame.Rect(24, y, 400, 36)
            selected = light.id == self.selected_id
            pygame.draw.rect(screen, ROW_ON if selected else ROW, row, border_radius=8)
            mark = "[x]" if light.id in group.light_ids else "[ ]"
            if not supports_color(light):
                mark = "[-]"
            screen.blit(
                self.font.render(f"{mark}  {light.attributes.custom_name}", True, TEXT),
                (row.x + 12, row.y + 9),
            )
            self._buttons.append((pygame.Rect(row.x, row.y, 44, row.h), lambda light=light: self._toggle_member(light)))
            self._buttons.append((pygame.Rect(row.x + 44, row.y, 200, row.h), lambda light=light: self._choose(light)))
            self._button(screen, pygame.Rect(286, y + 5, 58, 26), "On", lambda light=light: self._power(light, True))
            self._button(screen, pygame.Rect(352, y + 5, 58, 26), "Off", lambda light=light: self._power(light, False))

    def _draw_controls(self, screen) -> None:
        x = 460
        screen.blit(self.section_font.render("Show", True, TEXT), (x, 72))
        self._button(
            screen,
            pygame.Rect(x, 108, 200, 34),
            f"Pattern: {self.pattern_name}",
            self._cycle_pattern,
            enabled=not self.running,
        )
        if self.running:
            self._button(screen, pygame.Rect(x + 216, 108, 140, 34), "Stop", self._stop_show, primary=True)
        else:
            self._button(screen, pygame.Rect(x + 216, 108, 140, 34), "Start", self._start_show, primary=True)

        screen.blit(self.section_font.render("Group", True, TEXT), (x, 160))
        self._button(screen, pygame.Rect(x, 192, 200, 34), self._group().name, self._cycle_group)
        self._button(screen, pygame.Rect(x + 216, 192, 70, 34), "New", self._new_group)
        self._button(screen, pygame.Rect(x + 294, 192, 90, 34), "Delete", self._delete_group)

        screen.blit(self.section_font.render("Colors", True, TEXT), (x, 244))
        for index, (name, hues) in enumerate(PRESETS.items()):
            self._button(
                screen,
                pygame.Rect(x, 276 + index * 38, 380, 32),
                name,
                lambda hues=hues: self._set_hues(hues),
            )

        group = self._group()
        preset = next((name for name, hues in PRESETS.items() if hues == group.hues), "Custom ranges")
        screen.blit(self.font.render(preset, True, MUTED), (x, 394))
        screen.blit(self.font.render("Hue ranges", True, TEXT), (x, 422))
        self._hue_rect = pygame.Rect(x, 448, 400, 22)
        self._draw_hue_slider(screen, group)
        intensity_label = "Maximum intensity" if self.pattern_name == "strobe" else "Intensity"
        screen.blit(self.font.render(intensity_label, True, TEXT), (x, 484))
        self._level_rect = pygame.Rect(x, 510, 400, 22)
        self._draw_gradient(screen, self._level_rect, (28, 28, 36), (255, 255, 255))
        self._draw_handle(screen, self._level_rect, (group.level - 1) / 99)
        screen.blit(self.font.render(str(group.level), True, MUTED), (x + 408, 508))
        self._button(screen, pygame.Rect(x, 552, 160, 36), "Apply", self._apply_group, primary=True)

    def _draw_hue_slider(self, screen, group: Group) -> None:
        rect = self._hue_rect
        ranges = hue_ranges(group.hues)
        for pixel in range(rect.w):
            hue = hue_at(pixel, rect.w) % 360
            bright = any(hue_in_range(hue, start, end) for start, end in ranges)
            color = _hue_color(hue, 1.0 if bright else 0.35)
            pygame.draw.line(screen, color, (rect.x + pixel, rect.y), (rect.x + pixel, rect.y + rect.h))
        for start, end in ranges:
            for hue in (start, end):
                center = (int(rect.x + hue_position(hue, rect.w)), rect.centery)
                pygame.draw.circle(screen, (255, 255, 255), center, 9)
                pygame.draw.circle(screen, (24, 20, 40), center, 9, 2)

    def _draw_gradient(self, screen, rect: pygame.Rect, start: tuple[int, int, int], end: tuple[int, int, int]) -> None:
        for pixel in range(rect.w):
            blend = pixel / max(1, rect.w - 1)
            color = tuple(int(start[channel] + (end[channel] - start[channel]) * blend) for channel in range(3))
            pygame.draw.line(screen, color, (rect.x + pixel, rect.y), (rect.x + pixel, rect.y + rect.h))

    def _draw_handle(self, screen, rect: pygame.Rect, ratio: float) -> None:
        center = (int(rect.x + min(1.0, max(0.0, ratio)) * rect.w), rect.centery)
        pygame.draw.circle(screen, (255, 255, 255), center, 9)
        pygame.draw.circle(screen, (24, 20, 40), center, 9, 2)

    def _draw_room(self, screen) -> None:
        rect = self._room_rect()
        screen.blit(self.section_font.render("Room", True, TEXT), (rect.x, rect.y - 32))
        pygame.draw.rect(screen, PANEL, rect, border_radius=10)
        source = self._room_point(self.room.source_x, self.room.source_y)
        pygame.draw.circle(screen, (240, 200, 80), source, 12)
        screen.blit(self.font.render("Music", True, (240, 200, 80)), (source[0] + 16, source[1] - 8))
        for light in self.lights:
            if not self._in_any_group(light.id):
                continue
            layout = self.room.lights[light.id]
            point = self._room_point(layout.x, layout.y)
            color = (150, 176, 255) if light.id == self.selected_id else (214, 210, 230)
            pygame.draw.circle(screen, color, point, 14)
            screen.blit(self.font.render(light.attributes.custom_name, True, color), (point[0] + 18, point[1] - 8))

    def _button(self, screen, rect, label, action, primary: bool = False, enabled: bool = True) -> None:
        fill = (36, 34, 52) if not enabled else PRIMARY if primary else BUTTON
        pygame.draw.rect(screen, fill, rect, border_radius=8)
        text = self.font.render(label, True, MUTED if not enabled else TEXT)
        screen.blit(text, text.get_rect(center=rect.center))
        if enabled:
            self._buttons.append((rect, action))

    def _room_rect(self) -> pygame.Rect:
        return pygame.Rect(460, 680, 620, 160)

    def _room_point(self, x: float, y: float) -> tuple[int, int]:
        rect = self._room_rect()
        return (int(rect.x + x * rect.w), int(rect.y + y * rect.h))


def _font(size: int, bold: bool) -> pygame.font.Font:
    installed = {name.lower() for name in pygame.font.get_fonts()}
    for name in ("avenirnext", "futura", "helveticaneue", "helvetica"):
        if name in installed:
            return pygame.font.SysFont(name, size, bold=bold)
    return pygame.font.SysFont("sans", size, bold=bold)


def _hue_color(hue: float, value: float) -> tuple[int, int, int]:
    red, green, blue = colorsys.hsv_to_rgb((hue % 360) / 360, 1, value)
    return (int(red * 255), int(green * 255), int(blue * 255))


def _near(pos, point, radius: int = 16) -> bool:
    return (pos[0] - point[0]) ** 2 + (pos[1] - point[1]) ** 2 <= radius**2
