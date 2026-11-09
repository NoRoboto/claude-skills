# Placeholder SFX

`make_sfx.sh` synthesises five short mono 48 kHz WAVs with ffmpeg so the audio
pipeline works out of the box: `pop`, `whoosh`, `click`, `ding`, `thud`.
They are deliberately plain. Swap them for real recordings before publishing.

CC0 sources that need no attribution:

- https://freesound.org/search/?q=pop&f=license:%22Creative+Commons+0%22 (filter: license CC0)
- https://kenney.nl/assets?q=audio (UI, impact and interface packs, CC0)

Keep replacements short (< 500 ms for UI pops, < 1 s for whooshes), mono or
stereo, 44.1 or 48 kHz. `mix.py` resamples everything to 48 kHz stereo.
