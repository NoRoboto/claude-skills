#!/usr/bin/env python3
"""Burn storyboard captions (and optional narration) into the rendered video.

Usage: captions.py storyboard.json raw.mp4 final.mp4 [--audio narration.wav] [--font /path.ttf]
Caption style: bold dark text with thick white outline, upper third, fade in/out.
"""
import json
import os
import subprocess
import sys
import tempfile

FONT_CANDIDATES = [
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts", "ArchivoBlack-Regular.ttf"),
    "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/liberation-sans-fonts/LiberationSans-Bold.ttf",
]


def esc(s):
    return s.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\\\\\'").replace("%", "\\%")


def wrap(text, max_chars):
    if "\n" in text or len(text) <= max_chars:
        return text
    words, lines, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    lines.append(cur)
    return "\n".join(lines)


def main():
    a = sys.argv[1:]
    sb_path, src, dst = a[0], a[1], a[2]
    audio = a[a.index("--audio") + 1] if "--audio" in a else None
    font = a[a.index("--font") + 1] if "--font" in a else next((f for f in FONT_CANDIDATES if os.path.exists(f)), None)
    sb = json.load(open(sb_path))
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                            "-of", "csv=p=0", src], capture_output=True, text=True, check=True)
    width = int(probe.stdout.strip() or sb.get("width", 1080))
    size = int(width * sb.get("caption_scale", 0.062))
    max_chars = sb.get("caption_max_chars", 18)
    y = sb.get("caption_y", 0.12)
    fade = 0.15
    filters = []
    for c in sb.get("captions", []):
        t0, t1 = c["t0"], c["t1"]
        text = wrap(c["text"], max_chars)
        alpha = f"if(lt(t,{t0}+{fade}),(t-{t0})/{fade},if(gt(t,{t1}-{fade}),({t1}-t)/{fade},1))"
        filters.append(
            "drawtext=fontfile='%s':text='%s':fontsize=%d:fontcolor=0x1a1a1a:borderw=%d:bordercolor=white:shadowcolor=0x00000055:shadowx=3:shadowy=4"
            ":x=(w-text_w)/2:y=h*%s:line_spacing=8:text_align=center:enable='between(t,%s,%s)':alpha='%s'"
            % (font, esc(text), size, max(2, size // 11), y, t0, t1, alpha)
        )
    post = sb.get("post", {})
    if post.get("grain"):
        filters.append("noise=alls=%d:allf=t+u" % int(post["grain"]))
    if post.get("vignette"):
        filters.append("vignette=angle=PI/%s" % post.get("vignette_angle", 7))
    vf = ",".join(filters) if filters else "null"
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src]
    if audio:
        cmd += ["-i", audio]
    cmd += ["-vf", vf, "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    if audio:
        cmd += ["-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "160k", "-shortest"]
    cmd += [dst]
    subprocess.run(cmd, check=True)
    print("FINAL", dst)


main()
