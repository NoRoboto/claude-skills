# Look of the reference video ("Stupy Doo" solar explainer, 1080x1920, 60 fps)

Verified by frame extraction (2026-11-08): NOT AI-generated video. It is a 3D
scene with a cartoon render: geometry is identical across frames, line work is
stable, panels are exact clones that drop in one by one, the camera dollies and
pans over a fixed scene. AI, if any, was used for script / voice only.

## Visual recipe (what toonlib reproduces)

- Flat colours, one darker shadow band, no gradients: Diffuse → Shader to RGB →
  constant ColorRamp (shade 0.78 / lit 1.0) → Emission. View transform
  `Standard` (AgX/Filmic would wash the colours).
- Black outline ~3 px at 1080 wide: Freestyle, silhouette + crease + border,
  crease angle 140°.
- Palette: pale concrete roof (0.86,0.84,0.78), grass green (0.55,0.82,0.35),
  brown wall, blue panels with light cell grid (Brick texture on generated
  coords), white frames, black cable with yellow dashes, light-blue sky.
- Captions: heavy grotesque, dark text, thick white outline, top third,
  2–3 words, appear with the narration phrase.
- Motion: objects pop/drop in with overshoot (Back ease-out, 0.4–0.5 s, stagger
  0.1–0.15 s per clone); cable dashes travel to show current; devices flash;
  camera orbits slowly (10–20° over 4 s) and cuts hard between shots.
- Sun soft-shadow from upper-left-front: `sun_dir` (-0.5, 0.4, -1).

## Blender 5.1 gotchas (hit while building)

- `Curve.use_uv_as_generated` removed; bevelled curves already carry a UV with U
  along the length. `TexCoord.UV` → Mapping → Wave(BANDS, X, SAW) = dashes.
- Actions are slotted: `action.fcurves` is gone. Use `toonlib._fcurves(id)`,
  which walks `layers → strips → channelbags`.
- Video output: set `image_settings.media_type = "VIDEO"` before
  `file_format = "FFMPEG"`; PNG stills need `media_type = "IMAGE"`.
- Eevee id is `BLENDER_EEVEE` (detected at runtime; `_engine_id()`).
- Headless Eevee + Freestyle works with the NVIDIA driver, no display needed.
- `ShaderNodeMix` colour sockets: look up by identifier `A_Color`, `B_Color`,
  `Result_Color` (names are duplicated across data types).
- Fedora `dnf install blender` needs sudo; the user-space tarball lives in
  `~/.local/opt/blender`, symlink `~/.local/bin/blender`.

## What fixed the "cheap" first cut (acn-101 v1 -> v2)

1. Props, not boxes: `car`, `charger`, `transformer` prefabs; trees, poles, clouds as dressing.
2. One subject per shot, camera 8–13 m away, look point on the thing the caption names.
   Wide "whole site" shots read as empty; cut to the transformer instead of panning to it.
3. Cables `draw` on, then `flow`; devices `pulse` in the colour of the message (red = trip, green = OK).
4. Cool shadow tint, Archivo Black captions with white border + soft drop shadow, grain 5, vignette.
Still missing vs the reference: pencil hatching on the sky, soft contact shadows under objects,
hand-tuned asset detail (rails, bolts, windows). Use `model` with CC0 .glb packs for those.
