---
name: toon-explainer
description: "Trigger: explainer 3D, animacion tipo Stupy Doo, video explicativo cartoon, cel shading, toon animation, Blender animation, video vertical animado. Build and render cel-shaded 3D explainer videos from a storyboard.json with headless Blender."
license: Apache-2.0
metadata:
  author: "noroboto"
  version: "1.0"
---

## Activation Contract

Load when the user wants a cartoon / cel-shaded 3D explainer clip (flat colours, black outlines, objects popping in, moving camera, big captions), wants to reproduce a "Stupy Doo" style video, or asks to animate a diagram in Blender from text.

## Hard Rules

- Never generate the visuals with an image/video AI model. The look is 3D geometry + Freestyle outlines rendered by Blender.
- Blender binary: `~/.local/bin/blender` (5.1.x, user install). Always run headless with `-b -P`.
- Storyboard is the single source of truth: `storyboard.json` (schema in `references/storyboard-schema.md`). Edit JSON, re-render. Never hand-edit the `.blend`.
- Always look before rendering the full video: render `--stills` at 3–5 times, build a contact sheet, read it, fix overlaps / off-camera objects.
- Captions and audio are post-processing (`captions.py`), never Blender text objects.
- Narration in Spanish stays neutral; UI/caption copy follows the user's language.
- Keep clips short: 8–30 s per storyboard. Chain clips with ffmpeg concat for longer videos.

## Decision Gates

| Need | Do |
|------|----|
| Narrated video | Write narration first, time captions to it, then animate. Voice via `voice-video` skill (`tts.py`) and pass `--audio` to `captions.py`. |
| Quick look check | `--preview --stills t1,t2,t3` (half res, 8 samples). |
| Final render | No `--preview`; 1080x1920 default, 30 fps. |
| Object not in prefabs | Prefabs: box, plane, cylinder, sphere, panel, panel_row, cable, device, car, charger, transformer, cloud, tree, pole. Else compose from primitives, or `model` (glb/obj) with a path. |
| Frame looks cheap | One subject per shot, camera 8–13 m, add tree/pole/cloud dressing, cables `draw` then `flow`. See `references/style-notes.md`. |
| Manual tweak wanted | Add `--blend`, open `out/scene.blend` in the Blender UI. |

## Execution Steps

1. Read `references/storyboard-schema.md` and `references/style-notes.md`.
2. Write a small `gen.py` that emits `<workdir>/storyboard.json` (loops for rows of objects): objects on a ground plane at z=0, shots (orbit or from/to, one subject each), actions (drop_in, pop_in, slide_in, draw, flow, pulse, glow, move, color, hide, show), captions (t0, t1, text), `post`.
3. Stills: `~/.local/bin/blender -b -P ~/.claude/skills/toon-explainer/assets/build.py -- storyboard.json out --preview --stills 1,3,5`. Build a contact sheet with Pillow and read it.
4. Fix framing and timing in JSON. Repeat step 3 until every shot reads clearly.
5. Preview video: same command with `--preview` only. Check `out/raw.mp4` with ffprobe (duration, fps).
6. Captions + audio: `python3 ~/.claude/skills/toon-explainer/assets/captions.py storyboard.json out/raw.mp4 out/final.mp4 [--audio narration.wav]`.
7. Final: drop `--preview`, re-run steps 5–6. Open `out/final.mp4` with `xdg-open`.

## Output Contract

Return: path of `storyboard.json`, path of `out/final.mp4`, duration, resolution, and one line per shot describing what is on screen. Report render time. List anything not yet implemented (music, SFX, lip sync).

## References

- `references/storyboard-schema.md` — JSON schema, prefabs, actions, camera conventions.
- `references/style-notes.md` — look analysis of the reference video, palette, Blender 5 gotchas, what fixed the cheap first cut.
- `references/external/` — MIT copies: EL4CTEO `blender-stylized-npr` (toon_setup.py: bands, shadow tint, rim, inverted hull, Line Art) and arjun988 `camera-cinematography` (lens table, camera move library).
- `assets/toonlib.py` — bpy library (materials, prefabs, camera, animations).
- `assets/build.py` — storyboard → Blender render.
- `assets/captions.py` — ffmpeg captions + audio mux.
- `assets/storyboard.example.json` — solar rooftop example, 9 s.
