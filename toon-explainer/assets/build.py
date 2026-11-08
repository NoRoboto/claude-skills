"""Build and render a storyboard.json with Blender.

Usage (from any directory):
  blender -b -P build.py -- storyboard.json out_dir [--preview] [--stills 0.5,2,4] [--blend]

  --preview   half resolution, fewer samples, 15 fps (fast look check)
  --stills    render only PNGs at the given times (seconds) into out_dir/stills/
  --blend     save out_dir/scene.blend for manual tweaking in the Blender UI
Writes out_dir/raw.mp4 (no captions, no audio). Captions and audio: captions.py.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy  # noqa: E402
import toonlib as T  # noqa: E402


def main():
    argv = sys.argv[sys.argv.index("--") + 1:]
    sb_path, out_dir = argv[0], argv[1]
    preview = "--preview" in argv
    stills = None
    if "--stills" in argv:
        stills = [float(x) for x in argv[argv.index("--stills") + 1].split(",")]
    save_blend = "--blend" in argv
    os.makedirs(out_dir, exist_ok=True)

    with open(sb_path) as fh:
        sb = json.load(fh)
    palette = dict(T.PALETTE)
    palette.update({k: tuple(v) if isinstance(v, list) else v for k, v in sb.get("palette", {}).items()})
    for k, v in list(palette.items()):
        if isinstance(v, str):
            palette[k] = T.rgb(v)[:3]

    fps = sb.get("fps", 30)
    width, height = sb.get("width", 1080), sb.get("height", 1920)
    samples = sb.get("samples", 16)
    if preview:
        width, height, samples, fps = width // 2, height // 2, 8, max(10, fps // 2)

    T.reset_scene()
    scene = T.setup_scene(width=width, height=height, fps=fps, duration=sb["duration"], samples=samples,
                          sky=sb.get("sky", "sky"), sun_dir=tuple(sb.get("sun_dir", (-0.4, 0.3, -1.0))),
                          line_px=sb.get("line_px", 3.0) * (0.5 if preview else 1.0), palette=palette)

    objs = {}
    for spec in sb.get("objects", []):
        spec = dict(spec)
        oid = spec.pop("id")
        kind = spec.pop("type")
        spec.pop("parent", None)
        fn = T.PREFABS[kind]
        for key in ("pos", "size", "rot", "points", "offset"):
            if key in spec and isinstance(spec[key], list):
                spec[key] = [tuple(p) for p in spec[key]] if key == "points" else tuple(spec[key])
        if kind != "empty" and kind != "model":
            spec["palette"] = palette
        o = fn(oid, **spec)
        objs[oid] = o
    for spec in sb.get("objects", []):
        if "parent" in spec:
            objs[spec["id"]].parent = objs[spec["parent"]]

    cam, tgt = T.camera(lens=sb.get("lens", 35))
    T.shots(cam, tgt, sb["shots"], fps, lens_default=sb.get("lens", 35))

    for act in sb.get("actions", []):
        act = dict(act)
        target = objs[act.pop("target")]
        name = act.pop("anim")
        t = act.pop("t")
        for key in ("to", "by", "rot_by", "offset"):
            if key in act:
                act[key] = tuple(act[key])
        if name == "color":
            act["palette"] = palette
        T.ANIMS[name](target, t, fps, **act)

    if save_blend:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out_dir, "scene.blend"))

    if stills is not None:
        sd = os.path.join(out_dir, "stills")
        os.makedirs(sd, exist_ok=True)
        if hasattr(scene.render.image_settings, "media_type"):
            scene.render.image_settings.media_type = "IMAGE"
        scene.render.image_settings.file_format = "PNG"
        for t in stills:
            scene.frame_set(T._f(t, fps))
            scene.render.filepath = os.path.join(sd, f"t{t:05.2f}.png")
            bpy.ops.render.render(write_still=True)
            print("STILL", scene.render.filepath)
        return

    if hasattr(scene.render.image_settings, "media_type"):
        scene.render.image_settings.media_type = "VIDEO"  # Blender 5.x
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM" if preview else "HIGH"
    scene.render.ffmpeg.gopsize = fps
    scene.render.filepath = os.path.join(out_dir, "raw.mp4")
    bpy.ops.render.render(animation=True)
    print("VIDEO", scene.render.filepath)


main()
