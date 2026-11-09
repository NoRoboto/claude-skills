#!/usr/bin/env python3
"""Mix narration, music and SFX from the storyboard `audio` section into one WAV.

Usage: mix.py storyboard.json out.wav [--duration S]

audio section:
  "audio": {
    "narration": {"file": "narration.wav", "gain_db": 0},
    "music": {"file": "track.mp3", "gain_db": -16, "duck_db": -10, "fade_in": 0.3, "fade_out": 1.0},
    "sfx": [{"file": "sfx/pop.wav", "at": 1.6, "gain_db": -4},
            {"file": "sfx/whoosh.wav", "at": "action:3", "offset": -0.05},
            {"file": "sfx/pop.wav", "at": "action:panels/drop_in", "each": true}]
  }
`at`: seconds, "action:<index>" or "action:<target>/<anim>" (first match). `offset` is
added after resolution. `each` places one SFX per staggered child of a group action.
File paths are relative to the storyboard directory (sfx fall back to assets/sfx/).
Ducking: music is multiplied by a gain curve built from the narration envelope in 10 ms
blocks: gain ramps toward `duck_db` (20 ms attack) while narration is above -45 dBFS and
back to 0 dB (400 ms release) when it drops below. Very quiet speech is not ducked.
Output: 48 kHz stereo s16 WAV, limited at -0.45 dBFS.
"""
import json
import os
import subprocess
import sys

SFX_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sfx")


def group_count(sb, target):
    """Number of staggered instances an action on `target` produces."""
    objs = {o["id"]: o for o in sb.get("objects", [])}
    o = objs.get(target)
    if o is None:
        return 1
    if o.get("type") == "panel_row":
        return int(o.get("count", 6))
    kids = [c for c in sb.get("objects", []) if c.get("parent") == target]
    return len(kids) if kids else 1


def resolve_action(sb, ref):
    """Return (index, action) for "action:<index>" or "action:<target>/<anim>"."""
    key = ref.split(":", 1)[1]
    actions = sb.get("actions", [])
    if key.isdigit():
        i = int(key)
        if not 0 <= i < len(actions):
            raise SystemExit("mix.py: %r out of range (storyboard has %d actions)" % (ref, len(actions)))
        return i, actions[i]
    target, _, anim = key.partition("/")
    for i, a in enumerate(actions):
        if a.get("target") == target and (not anim or a.get("anim") == anim):
            return i, a
    raise SystemExit("mix.py: no action matches %r" % ref)


def resolve_sfx(sb, base):
    """Expand the sfx list into concrete (time, path, gain_db) cues."""
    cues = []
    for s in sb.get("audio", {}).get("sfx", []):
        path = s["file"]
        if not os.path.isabs(path):
            cand = os.path.join(base, path)
            path = cand if os.path.exists(cand) else os.path.join(SFX_DIR, os.path.basename(path))
        if not os.path.exists(path):
            raise SystemExit("mix.py: sfx file not found: %s" % s["file"])
        gain = float(s.get("gain_db", 0))
        offset = float(s.get("offset", 0))
        at = s["at"]
        if isinstance(at, str) and at.startswith("action:"):
            _, act = resolve_action(sb, at)
            t0 = float(act["t"])
            stagger = float(act.get("stagger", 0))
            n = group_count(sb, act["target"]) if (s.get("each") and stagger > 0) else 1
            times = [t0 + i * stagger for i in range(n)]
        else:
            times = [float(at)]
        for t in times:
            cues.append((max(0.0, t + offset), path, gain))
    cues.sort()
    return cues


def duck_curve(narr_path, duck_db, duration, out_path, attack=0.02, release=0.4, floor_db=-45.0):
    """Write a stereo f32 gain curve: 1.0 where narration is silent, duck gain under speech."""
    import numpy as np
    sr = 48000
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", narr_path, "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    y = np.frombuffer(raw, dtype=np.float32)
    n = int(duration * sr)
    y = np.pad(y, (0, max(0, n - len(y))))[:n]
    block = sr // 100  # 10 ms
    nb = n // block
    rms = np.sqrt((y[:nb * block].reshape(nb, block) ** 2).mean(axis=1))
    speech = 20 * np.log10(rms + 1e-9) > floor_db
    target = np.where(speech, 10 ** (duck_db / 20.0), 1.0).astype(np.float32)
    # One-pole smoothing: fast attack (gain falls), slow release (gain rises).
    ca, cr = np.exp(-0.01 / attack), np.exp(-0.01 / release)
    g, cur = np.empty_like(target), 1.0
    for i, t in enumerate(target):
        c = ca if t < cur else cr
        cur = c * cur + (1 - c) * t
        g[i] = cur
    curve = np.repeat(g, block)
    curve = np.pad(curve, (0, n - len(curve)), mode="edge")
    np.repeat(curve, 2).astype(np.float32).tofile(out_path)


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        raise SystemExit(__doc__)
    sb_path, out = a[0], a[1]
    sb = json.load(open(sb_path))
    base = os.path.dirname(os.path.abspath(sb_path))
    duration = float(a[a.index("--duration") + 1]) if "--duration" in a else float(sb["duration"])
    audio = sb.get("audio", {})
    narr = audio.get("narration")
    music = audio.get("music")
    cues = resolve_sfx(sb, base)

    inputs, chains, mix_labels, tmp = [], [], [], []

    def add_input(path, fmt=None):
        if fmt:
            inputs.extend(fmt)
        inputs.extend(["-i", path])
        return len([x for x in inputs if x == "-i"]) - 1

    def absolute(p):
        return p if os.path.isabs(p) else os.path.join(base, p)

    def require(path, what):
        if not os.path.exists(path):
            raise SystemExit("mix.py: %s file not found: %s" % (what, path))
        return path

    if narr:
        i = add_input(require(absolute(narr["file"]), "narration"))
        chains.append("[%d:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=%sdB[nar]" % (i, float(narr.get("gain_db", 0))))
        mix_labels.append("[nar]")
    if music:
        i = add_input(require(absolute(music["file"]), "music"))
        fin, fout = float(music.get("fade_in", 0.3)), float(music.get("fade_out", 1.0))
        chain = ("[%d:a]aformat=sample_rates=48000:channel_layouts=stereo,atrim=0:%s,asetpts=PTS-STARTPTS,"
                 "apad=whole_dur=%s,volume=%sdB,afade=t=in:d=%s,afade=t=out:st=%s:d=%s"
                 % (i, duration, duration, float(music.get("gain_db", -16)), fin, max(0.0, duration - fout), fout))
        if narr and music.get("duck_db") is not None:
            gain_path = out + ".duck.f32"
            tmp.append(gain_path)
            try:
                duck_curve(absolute(narr["file"]), float(music["duck_db"]), duration, gain_path)
            except Exception:
                if os.path.exists(gain_path):
                    os.remove(gain_path)
                raise
            g = add_input(gain_path, ["-f", "f32le", "-ar", "48000", "-ac", "2"])
            chain += "[mus0];[mus0][%d:a]amultiply[mus]" % g
        else:
            chain += "[mus]"
        chains.append(chain)
        mix_labels.append("[mus]")

    print("SFX cues (%d):" % len(cues))
    for k, (t, path, gain) in enumerate(cues):
        i = add_input(path)
        ms = int(round(t * 1000))
        chains.append("[%d:a]aformat=sample_rates=48000:channel_layouts=stereo,volume=%sdB,adelay=%d|%d[s%d]" % (i, gain, ms, ms, k))
        mix_labels.append("[s%d]" % k)
        shown = os.path.relpath(path, base) if path.startswith(base) else path
        print("  %7.3f s  %+5.1f dB  %s" % (t, gain, shown))

    if not mix_labels:
        raise SystemExit("mix.py: nothing to mix (no narration, music or sfx)")
    if len(mix_labels) == 1:
        chains.append("%sanull[pre]" % mix_labels[0])
    else:
        chains.append("%samix=inputs=%d:normalize=0:dropout_transition=0[pre]" % ("".join(mix_labels), len(mix_labels)))
    chains.append("[pre]atrim=0:%s,apad=whole_dur=%s,alimiter=limit=0.95:level=false[out]" % (duration, duration))

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"] + inputs + [
        "-filter_complex", ";".join(chains), "-map", "[out]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", out]
    try:
        subprocess.run(cmd, check=True)
    finally:
        for p in tmp:
            if os.path.exists(p):
                os.remove(p)
    print("MIX", out, "%.2f s" % duration)


main()
