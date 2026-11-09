#!/usr/bin/env python3
"""Beat detection and beat-snapping for storyboard timings (numpy + ffmpeg only).

Usage:
  beats.py detect music.mp3 [--bpm-min 70] [--bpm-max 180] [--json beats.json]
  beats.py snap storyboard.json --music music.mp3 [--tolerance 0.25] [--captions] [--write]

detect: prints BPM and beat times. snap: moves each action `t` (and caption t0/t1 with
--captions) to the nearest beat when |delta| <= tolerance; actions with "snap": false
are left alone. --write rewrites the storyboard in place (key order preserved).
"""
import json
import subprocess
import sys

import numpy as np

SR = 22050
HOP = 256
NFFT = 1024


def decode(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def onset_envelope(y):
    """Half-wave rectified log-magnitude spectral flux per hop (centred frames)."""
    # Centred frames: frame i is the window around sample i * HOP, so a flux
    # peak lands on the onset instead of one window length before it.
    y = np.pad(y, (NFFT // 2, NFFT // 2))
    n = 1 + max(0, (len(y) - NFFT) // HOP)
    win = np.hanning(NFFT).astype(np.float32)
    idx = np.arange(NFFT)[None, :] + HOP * np.arange(n)[:, None]
    frames = y[idx] * win
    mag = np.abs(np.fft.rfft(frames, axis=1))
    logmag = np.log1p(1000.0 * mag)
    flux = np.diff(logmag, axis=0, prepend=logmag[:1])
    env = np.maximum(flux, 0).sum(axis=1)
    env -= env.min()
    if env.max() > 0:
        env /= env.max()
    # Remove slow trend so sustained notes do not look like onsets.
    k = int(0.5 * SR / HOP) | 1
    trend = np.convolve(env, np.ones(k) / k, mode="same")
    return np.maximum(env - trend, 0)


def tempo(env, bpm_min, bpm_max):
    fps = SR / HOP
    lag_min, lag_max = int(fps * 60 / bpm_max), int(fps * 60 / bpm_min)
    if not (0 < bpm_min < bpm_max):
        raise SystemExit("beats.py: need 0 < --bpm-min < --bpm-max (got %g, %g)" % (bpm_min, bpm_max))
    if env.max() <= 0:
        raise SystemExit("beats.py: no onsets found (silent audio?)")
    e = env - env.mean()
    # Autocorrelation via FFT (O(n log n)); zero-pad to 2n to avoid wrap-around.
    spec = np.fft.rfft(e, 2 * len(e))
    ac = np.fft.irfft(spec * np.conj(spec))[:len(e)]
    ac /= ac[0] if ac[0] else 1
    lags = np.arange(len(ac))
    window = (lags >= lag_min) & (lags <= lag_max)
    if not window.any():
        raise SystemExit("beats.py: track too short for the BPM range")
    peak, mean = ac[window].max(), np.abs(ac[window]).mean()
    # Synthetic click/music beds score peak 0.6-0.95 and ratio ~13; pink noise 0.04 / 3.4.
    if peak < 0.15 or peak < 4.0 * mean:
        raise SystemExit("beats.py: no clear periodicity (autocorrelation peak %.3f vs mean %.3f); "
                         "not snapping to a fabricated tempo" % (peak, mean))
    # Mild preference for lags near 120 BPM to break octave ties.
    prior = np.exp(-0.5 * ((np.log2(lags[window] * 60 / fps / 120.0)) / 1.0) ** 2)
    lag = lags[window][np.argmax(ac[window] * prior)]
    # Parabolic refinement.
    if 1 <= lag < len(ac) - 1:
        a, b, c = ac[lag - 1], ac[lag], ac[lag + 1]
        d = (a - c) / (2 * (a - 2 * b + c)) if (a - 2 * b + c) else 0
        lag = lag + d
    return 60.0 * fps / lag


def beat_grid(env, bpm, snap_s=0.07):
    fps = SR / HOP
    period = 60.0 / bpm * fps
    n_beats = int(len(env) / period)
    phases = np.arange(0, period, 0.25)
    best, best_score = 0.0, -1
    k = np.arange(n_beats)
    for ph in phases:
        pos = np.round(ph + k * period).astype(int)
        pos = pos[pos < len(env)]
        score = env[pos].sum()
        if score > best_score:
            best, best_score = ph, score
    beats = best + k * period
    beats = beats[beats < len(env)]
    # Snap each beat to the strongest onset within +-snap_s.
    r = int(snap_s * fps)
    out = []
    for b in beats:
        c = int(round(b))
        lo, hi = max(0, c - r), min(len(env), c + r + 1)
        if hi > lo and env[lo:hi].max() > 0.05:
            c = lo + int(np.argmax(env[lo:hi]))
        out.append(c / fps)
    return np.array(out)


def detect(path, bpm_min=70, bpm_max=180):
    y = decode(path)
    env = onset_envelope(y)
    bpm = tempo(env, bpm_min, bpm_max)
    return bpm, beat_grid(env, bpm)


def nearest(t, beats):
    i = int(np.argmin(np.abs(beats - t)))
    return float(beats[i])


def cmd_detect(a):
    path = a[0]
    bpm_min = float(a[a.index("--bpm-min") + 1]) if "--bpm-min" in a else 70
    bpm_max = float(a[a.index("--bpm-max") + 1]) if "--bpm-max" in a else 180
    bpm, beats = detect(path, bpm_min, bpm_max)
    print("BPM %.2f  beats %d  first %.3f s" % (bpm, len(beats), beats[0] if len(beats) else -1))
    print(" ".join("%.3f" % b for b in beats))
    if "--json" in a:
        json.dump({"bpm": round(bpm, 3), "beats": [round(float(b), 4) for b in beats]},
                  open(a[a.index("--json") + 1], "w"), indent=2)


def cmd_snap(a):
    sb_path = a[0]
    music = a[a.index("--music") + 1]
    tol = float(a[a.index("--tolerance") + 1]) if "--tolerance" in a else 0.25
    bpm, beats = detect(music)
    if len(beats) == 0:
        raise SystemExit("beats.py: no beats detected in %s" % music)
    sb = json.load(open(sb_path))
    moved = 0
    print("BPM %.2f  tolerance %.2f s" % (bpm, tol))
    for i, act in enumerate(sb.get("actions", [])):
        if act.get("snap") is False:
            continue
        t = float(act["t"])
        b = nearest(t, beats)
        if 0 < abs(b - t) <= tol:
            print("  action %2d %-14s %-9s %7.3f -> %7.3f (%+.3f)" % (i, act["target"], act["anim"], t, b, b - t))
            act["t"] = round(b, 3)
            moved += 1
    if "--captions" in a:
        for c in sb.get("captions", []):
            for key in ("t0", "t1"):
                t = float(c[key])
                b = nearest(t, beats)
                if 0 < abs(b - t) <= tol:
                    print("  caption %-20s %s %7.3f -> %7.3f" % (c["text"][:20], key, t, b))
                    c[key] = round(b, 3)
                    moved += 1
    print("moved %d" % moved)
    if "--write" in a:
        json.dump(sb, open(sb_path, "w"), indent=2)
        print("WROTE", sb_path)


def main():
    a = sys.argv[1:]
    if len(a) < 2 or a[0] not in ("detect", "snap"):
        raise SystemExit(__doc__)
    (cmd_detect if a[0] == "detect" else cmd_snap)(a[1:])


main()
