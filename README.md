# claude-skills

Skills for [Claude Code](https://claude.com/claude-code). Each folder is one skill: a `SKILL.md` runtime contract plus `assets/` (scripts, templates) and `references/` (notes the skill tells the agent to read).

## Install

```bash
git clone https://github.com/NoRoboto/claude-skills.git
ln -s "$PWD/claude-skills/toon-explainer" ~/.claude/skills/toon-explainer
```

Claude Code picks up every folder under `~/.claude/skills/` that has a `SKILL.md`.

## Skills

### toon-explainer

Cel-shaded 3D explainer clips (flat colours, black outlines, objects popping in, moving camera, big captions) rendered by headless Blender from a declarative `storyboard.json`. The agent writes the JSON, renders stills to check framing, then renders the video and burns captions and narration with ffmpeg.

Pipeline:

```
storyboard.json -> build.py (bpy: prefabs, camera shots, animations, Freestyle outlines)
               -> raw.mp4 -> captions.py (ffmpeg drawtext, optional --audio) -> final.mp4
```

Requirements: Blender 5.1+ on PATH (the skill looks for `~/.local/bin/blender`; edit the path in `SKILL.md` if yours differs), ffmpeg with `drawtext`, Python 3 with Pillow for contact sheets.

Try it:

```bash
blender -b -P toon-explainer/assets/build.py -- toon-explainer/assets/storyboard.example.json out --preview
python3 toon-explainer/assets/captions.py toon-explainer/assets/storyboard.example.json out/raw.mp4 out/final.mp4
```

Docs: `toon-explainer/references/storyboard-schema.md` (objects, shots, actions, captions) and `toon-explainer/references/style-notes.md` (the look, Blender 5 gotchas, what makes a frame read well).

## Third-party material

- `toon-explainer/assets/fonts/ArchivoBlack-Regular.ttf`: Archivo Black, SIL Open Font License (see `OFL.txt` next to it).
- `toon-explainer/references/external/`: MIT-licensed copies of two reference skills, with their licenses: `blender-stylized-npr` from [EL4CTEO/blender-skills](https://github.com/EL4CTEO/blender-skills) and `camera-cinematography` from [arjun988/blender-skills](https://github.com/arjun988/blender-skills).

## License

MIT, see `LICENSE`.
