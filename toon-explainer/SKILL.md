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
- Captions and audio are post-processing (`mix.py`, `captions.py`), never Blender text objects.
- SFX land on action times via `action:` refs in the `audio` section, never hand-typed seconds when an action exists.
- Narration in Spanish stays neutral; UI/caption copy follows the user's language.
- Keep clips short: 8–30 s per storyboard. Chain clips with ffmpeg concat for longer videos.

## Decision Gates

| Need | Do |
|------|----|
| Narrated video | Narration first, captions timed to it, then animate. Voice via `voice-video` (`tts.py`) into `audio.narration`. |
| SFX / music | `audio` section: narration, music, sfx with `action:` refs. Placeholders in `assets/sfx/`, CC0 sources in its README. |
| Music provided | `beats.py snap storyboard.json --music track.mp3 --write` before stills. |
| Quick look check | `--preview --stills t1,t2,t3` (half res, 8 samples). |
| Final render | No `--preview`; 1080x1920 default, 30 fps. |
| Object not in prefabs | Prefabs: box, plane, cylinder, sphere, panel, panel_row, cable, device, car, charger, transformer, cloud, tree, pole. Else primitives or `model` (glb/obj). |
| Frame looks cheap | One subject per shot, camera 8–13 m, tree/pole/cloud dressing, cables `draw` then `flow`. See `references/style-notes.md`. |
| Manual tweak wanted | Add `--blend`, open `out/scene.blend` in the Blender UI. |

## Execution Steps

1. Read `references/storyboard-schema.md` and `references/style-notes.md`.
2. Write a small `gen.py` that emits `<workdir>/storyboard.json`: objects on a ground plane at z=0, shots (one subject each), actions, captions, `post`, `audio`.
3. Stills: `~/.local/bin/blender -b -P ~/.claude/skills/toon-explainer/assets/build.py -- storyboard.json out --preview --stills 1,3,5`. Build a contact sheet with Pillow and read it.
4. Fix framing and timing in JSON. Repeat step 3 until every shot reads clearly.
5. Preview video: same command with `--preview` only. Check `out/raw.mp4` with ffprobe (duration, fps).
6. Audio (if `audio` present): `python3 ~/.claude/skills/toon-explainer/assets/mix.py storyboard.json out/mix.wav`. Read the cue table.
7. Captions + mux: `python3 ~/.claude/skills/toon-explainer/assets/captions.py storyboard.json out/raw.mp4 out/final.mp4 --audio out/mix.wav` (or `--audio narration.wav` without `audio`).
8. Final: drop `--preview`, re-run steps 5–7. Open `out/final.mp4` with `xdg-open`.

## Output Contract

Return: path of `storyboard.json`, path of `out/final.mp4`, duration, resolution, and one line per shot describing what is on screen. Report render time. List anything not yet implemented (lip sync, multi-clip concat).

## References

- `references/storyboard-schema.md` — JSON schema, prefabs, actions, camera conventions.
- `references/style-notes.md` — reference look, Blender 5 gotchas, what fixed the cheap cut, sound design.
- `references/external/` — MIT copies: EL4CTEO `blender-stylized-npr`, arjun988 `camera-cinematography`.
- `assets/toonlib.py` — bpy library (materials, prefabs, camera, animations).
- `assets/build.py` — storyboard → Blender render.
- `assets/mix.py` — `audio` section to one WAV (ducked music, SFX cues).
- `assets/beats.py` — beat detect + snap action times.
- `assets/sfx/` — placeholder SFX, CC0 sources.
- `assets/captions.py` — ffmpeg captions + audio mux.
- `assets/storyboard.example.json` — solar rooftop example, 9 s.
