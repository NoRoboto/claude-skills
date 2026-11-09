#!/usr/bin/env bash
# Generate placeholder SFX with ffmpeg (mono 48 kHz, 16-bit). No downloads.
# Usage: bash make_sfx.sh [out_dir]   (default: this directory)
set -euo pipefail
OUT="${1:-$(dirname "$0")}"
FF=(ffmpeg -y -hide_banner -loglevel error)
# pop: sine sweep 600 -> 200 Hz over 90 ms with exponential decay
"${FF[@]}" -f lavfi -i "aevalsrc=0.8*sin(2*PI*(600*t-200*t*t/0.09))*exp(-t*35):s=48000:d=0.09" \
  -af "afade=t=in:d=0.002,afade=t=out:st=0.07:d=0.02" -ac 1 -c:a pcm_s16le "$OUT/pop.wav"
# whoosh: bandpass-swept noise, 350 ms
"${FF[@]}" -f lavfi -i "anoisesrc=color=pink:amplitude=0.9:s=48000:d=0.35" \
  -af "bandpass=f=900:w=600,volume='1.6*sin(PI*t/0.35)':eval=frame,afade=t=out:st=0.28:d=0.07" \
  -ac 1 -c:a pcm_s16le "$OUT/whoosh.wav"
# click: 5 ms burst
"${FF[@]}" -f lavfi -i "aevalsrc=sin(2*PI*3000*t)*exp(-t*800):s=48000:d=0.005" \
  -ac 1 -c:a pcm_s16le "$OUT/click.wav"
# ding: 1760 Hz with 400 ms decay
"${FF[@]}" -f lavfi -i "aevalsrc=(sin(2*PI*1760*t)+0.3*sin(2*PI*3520*t))*exp(-t*8):s=48000:d=0.4" \
  -af "afade=t=in:d=0.002,afade=t=out:st=0.35:d=0.05" -ac 1 -c:a pcm_s16le "$OUT/ding.wav"
# thud: 60 Hz with pitch drop, 200 ms
"${FF[@]}" -f lavfi -i "aevalsrc=sin(2*PI*(60+40*exp(-t*30))*t)*exp(-t*14):s=48000:d=0.2" \
  -af "afade=t=out:st=0.15:d=0.05" -ac 1 -c:a pcm_s16le "$OUT/thud.wav"
ls -l "$OUT"/*.wav
