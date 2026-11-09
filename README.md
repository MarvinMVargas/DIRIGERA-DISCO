# Dirigera Disco

App to sync Dirigera Hub connected RGB lights to microphone input (music mostly). Three different light patterns to choose, some preset color ranges, and manual controls for defining yours.

## Walking on the shoulders of giants

This is specially possible thanks to [Nicolas Hilberg](https://github.com/Leggin) who wrote the [Dirigera module](https://github.com/Leggin/dirigera) for python to be able to control the hub and interact with the devices.

## AI disclaimer

This was 100% vibecoded in a night. I gave a slight look at the code but there may be issues still with it.

## Setup

Requires Python 3.13. From the project directory:

```bash
uv sync
```

Find the hub IP on the local network, then generate a token. When asked, press the action button on the bottom of the hub, then press Enter:

```bash
generate-token <hub-ip>
```

Copy `.env.example` to `.env` and set `DIRIGERA_IP` and `DIRIGERA_TOKEN`. The token stays out of source control.

## Show window

```bash
uv run python -m dirigera_disco gui
```

The window lists the hub's lights. Mark a light to put it in the active group. On and Off control that bulb directly.

**Groups.** Cycle the group name to edit another group. New copies the current hue ranges and intensity into an empty group. Delete removes the active group and keeps at least one. A light can belong to more than one group. The show uses every light that is in any group. A light in the active group uses that group's colors and intensity; otherwise it uses the first group that contains it.

**Colors.** Three presets set the hue ranges: Blue and pink, Green and purple, and Red, orange, blue, and yellow. The hue bar can hold up to eight ranges. Drag a handle to move one end of a range. Click an empty part of the bar to add a range. Right-click a range to remove it. One range always remains.

**Intensity.** Flow and jump hold this level for the whole show, including while the color changes. Strobe uses it as the bright peak and drops to the lowest level in between. The label reads Maximum intensity while strobe is selected.

**Apply** sends the first hue in the active group, at full saturation, and the intensity to that group's reachable color lights. Apply is available only while the show is stopped.

**Patterns.** Flow fades from one chosen hue to the next over two seconds. Jump snaps to the next hue on each beat from the microphone, so play music near the Mac while jump is running. Strobe alternates a chosen hue and darkness twice a second. The pattern button is locked while a show is playing. Stop the show before changing it. Start and Stop run the show for every grouped color light the hub can reach. Closing the window stops the show and leaves the last color in place.

**Room.** Drag grouped lights and the music marker to store a layout in `room.json`. The layout is saved for a later effect and does not change the current patterns. Groups, hue ranges, and intensity are saved in the same file.

## Commands

Repeat `--name` to choose specific lights. Omit it to use every reachable light.

```bash
uv run python -m dirigera_disco list
uv run python -m dirigera_disco on --name "Floor Lamp"
uv run python -m dirigera_disco off
uv run python -m dirigera_disco color --hue 30 --saturation 0.8 --name "Floor Lamp"
uv run python -m dirigera_disco cycle --pattern flow --palette rainbow --seconds 20
```

`list` prints each light's name, id, whether the hub can reach it, whether it is on, and whether it accepts color.

`color` sets hue from 0 to 360 and saturation from 0 to 1. Bulbs that cannot show a color are skipped.

`cycle` runs one pattern for the given number of seconds. Patterns are `flow`, `jump`, and `strobe`. Palettes are `rainbow`, `warm`, `cool`, and `party`. Every selected bulb receives the same step together. Here, flow fades over two seconds, and jump and strobe step on a timer rather than the microphone. Ctrl-C leaves the lights on the last update.
