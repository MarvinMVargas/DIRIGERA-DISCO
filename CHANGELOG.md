# Changelog

## 1.0.0 — 2026-11-09

First release of Dirigera Disco.

- Connect to a Dirigera hub with `DIRIGERA_IP` and `DIRIGERA_TOKEN`.
- List lights, turn them on or off, and set hue and saturation from the command line.
- Run flow, jump, and strobe from the command line against a shared palette. Flow fades on the bulb over two seconds, and updates for every selected light go out together.
- Open a pygame window that groups lights and saves those groups, hue ranges, intensity, and a room layout in `room.json`.
- Choose colors with presets or with up to eight hue ranges on one slider.
- Hold one intensity for flow and jump. Strobe uses that intensity as its bright peak and the lowest level as its dark step.
- Snap jump to the next color on each microphone beat. Flow and strobe keep their own timing.
- Lock the pattern control while a show is playing.
