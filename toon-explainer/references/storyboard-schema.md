# storyboard.json schema

Coordinates: metres. X right, Y away from the default camera, Z up. Put the main
surface (roof, table, ground) at z = 0 so object `pos` z values stay small.
Times in seconds. Frame 1 = t 0.

```json
{
  "fps": 30, "width": 1080, "height": 1920, "duration": 9.0,
  "lens": 35, "samples": 16, "line_px": 3.0,
  "sky": "sky", "sun_dir": [-0.5, 0.4, -1.0],
  "palette": {"brand": "#ff6600"},
  "objects": [...], "shots": [...], "actions": [...], "captions": [...],
  "caption_scale": 0.062, "caption_max_chars": 18, "caption_y": 0.12
}
```

## objects

Every object: `id`, `type`, optional `parent` (id of an `empty` or group).
Colours: palette key, `#hex`, or `[r,g,b]` 0–1. Palette keys in `toonlib.PALETTE`:
concrete, grass, wall, wall_light, panel, panel_cell, frame, metal, cable, dash,
white, black, sky, sun, tank, wood, red, green. Extend with top-level `palette`.

| type | fields | notes |
|------|--------|-------|
| `box` | size [x,y,z], pos, rot (deg), color, shade (0.78), grid | pos is the centre |
| `plane` | size [x,y], pos, color | ground |
| `cylinder` | radius, height, pos, rot, color | tanks, posts |
| `sphere` | radius, pos, color | bulbs, suns |
| `panel` | pos, size [w,l], tilt (deg), rot_z, color, frame | one solar panel, parent empty |
| `panel_row` | count, pos, size, tilt, gap, axis ("x"/"y"), rot_z | children `<id>_0..n` |
| `cable` | points [[x,y,z],...], radius, color, dash, period (m), smooth | bevelled curve, dashes move with `flow` |
| `device` | size, pos, rot, color, screen | wall box with screen (inverter, meter) |
| `car` | pos, rot_z, color, length (4.2) | body, cabin, glass, lights, 4 wheels; nose toward -Y |
| `charger` | pos, rot_z, color, screen | L2 pedestal: post, head, screen, plug, hose; screen faces -Y |
| `transformer` | pos (base at z), size [w,d,h], rot_z | pad-mount cabinet with fins, door, warning plate; front -Y |
| `cloud` | pos, scale | three merged spheres, flat white |
| `tree` | pos, scale, color | trunk + two canopy spheres |
| `pole` | pos, height | utility pole with head |
| `model` | path (.glb/.gltf/.obj/.fbx), pos, scale, rot | external asset under an empty |
| `empty` | pos | group parent |

Things that are hidden until an action shows them must still be placed at their final position.
Shadows are tinted cool (`toonlib.SHADOW_TINT`), not grey; pass `shade` (float or [r,g,b]) on box/sphere to override.

Scene dressing that makes a frame read as "a place" instead of boxes on a plane: 2–4 `tree`,
1–2 `pole` along the back edge, 2–3 `cloud` at z 9–12 and y 24–30, a `curb` box along the row.

## shots

Camera cuts hard between shots; inside a shot it eases (sine in/out).

```json
{"t0": 0, "t1": 4.5, "orbit": {"center": [0,0,0], "radius": 16, "height": 9, "angle_from": -70, "angle_to": -50}}
{"t0": 4.5, "t1": 9, "from": {"pos": [6,-12,4], "look": [2,-3,0]}, "to": {"pos": [5,-9,2.5], "look": [3,-4,-0.6]}, "lens": 35}
```

Orbit angle: degrees around Z, -90 = camera on -Y looking toward +Y. Vertical
1080x1920 frame with lens 35: at radius 16 / height 9 a 12 m roof fills the width.
Closer: radius 6–8 for a single device. Keep `look` on the object the caption names.

## actions

`{"target": id, "anim": name, "t": seconds, ...}`. Targets that are groups
(`panel_row`, `empty` with children) stagger their children by `stagger` seconds.

| anim | params | effect |
|------|--------|--------|
| `drop_in` | dur 0.5, height 3, stagger 0.12 | hidden, then falls into place with overshoot |
| `pop_in` | dur 0.4, stagger 0.1 | hidden, then scales up with overshoot |
| `slide_in` | dur 0.5, offset [-4,0,0], stagger | hidden, then slides in |
| `hide` | — | disappears at t |
| `show` | — | reappears at t (after a `hide`) |
| `draw` | dur 0.8 | cable grows along its path (bevel_factor_end) |
| `move` | dur 1, to / by [x,y,z], rot_by [deg] | translate / rotate |
| `pulse` | dur 1, strength 0.6, times 2 | emission flashes (alarm, "it works") |
| `glow` | dur 0.3, strength 0.35, off_at | emission stays on (bulb lights) |
| `flow` | speed m/s 3, dur or stop_at | cable dashes travel; stop_at freezes them (power cut) |
| `color` | color, dur 0.2 | recolour a plain material (not grid) |

Emission adds to an already bright base: on saturated light colours (sun, white) even 0.35 clips to white. Use glow/pulse on mid-tone colours, or strength 0.15, or give the object a darker base colour and let the glow lift it.

## post (captions.py)

`"post": {"grain": 5, "vignette": true, "vignette_angle": 7}` adds film grain and a
soft vignette after the captions. Font default: `assets/fonts/ArchivoBlack-Regular.ttf`
(OFL), override with `--font`.

## captions

`{"t0", "t1", "text"}`; drawn centred at `caption_y` of the height, bold, dark
with white outline, auto-wrapped at `caption_max_chars`. Keep 1–4 words, one idea,
aligned to the narration phrase. Use `\n` to force a break.

## commands

```
~/.local/bin/blender -b -P ~/.claude/skills/toon-explainer/assets/build.py -- storyboard.json out [--preview] [--stills 1,3,5] [--blend]
python3 ~/.claude/skills/toon-explainer/assets/captions.py storyboard.json out/raw.mp4 out/final.mp4 [--audio narration.wav] [--font file.ttf]
```

Render cost on this machine (RTX 5060 Ti): preview 9 s clip ≈ 13 s; 1080x1920
30 fps ≈ 0.3 s/frame.

## Framing lesson (acn-101, 2026-11-08)

Vertical 1080x1920 with lens 35 has a horizontal half-FOV of ~16 deg (lens 28: ~20 deg). At 25 m camera distance only +-7 m around the look point is visible. Keep every object the caption names within that band, or use `lens: 28` on the shot. Cluster props (transformer, controller) within ~8 m of the charger row instead of spreading them realistically.
