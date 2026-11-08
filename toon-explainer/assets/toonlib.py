"""Blender (bpy) helpers for cel-shaded explainer animations.

Run inside Blender only. Coordinate convention: X right, Y away from camera, Z up.
"""
import math
import bpy
from mathutils import Vector

PALETTE = {
    "concrete": (0.86, 0.84, 0.78),
    "grass": (0.55, 0.82, 0.35),
    "wall": (0.60, 0.42, 0.35),
    "wall_light": (0.93, 0.86, 0.78),
    "panel": (0.22, 0.30, 0.72),
    "panel_cell": (0.78, 0.85, 1.00),
    "frame": (0.92, 0.92, 0.94),
    "metal": (0.80, 0.82, 0.85),
    "cable": (0.12, 0.12, 0.12),
    "dash": (1.00, 0.85, 0.20),
    "white": (0.96, 0.96, 0.96),
    "black": (0.08, 0.08, 0.08),
    "sky": (0.72, 0.86, 1.00),
    "sun": (1.00, 0.80, 0.25),
    "tank": (0.15, 0.15, 0.15),
    "wood": (0.85, 0.70, 0.45),
    "red": (0.90, 0.25, 0.20),
    "green": (0.30, 0.75, 0.35),
}


def rgb(c, palette=None):
    """Accept palette key, hex string or (r,g,b) tuple. Return RGBA."""
    palette = palette or PALETTE
    if isinstance(c, str):
        if c.startswith("#"):
            h = c.lstrip("#")
            c = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        else:
            c = palette[c]
    return (c[0], c[1], c[2], 1.0)


# ---------------------------------------------------------------- scene setup

def _engine_id():
    ids = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    for cand in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"):
        if cand in ids:
            return cand
    return "BLENDER_WORKBENCH"


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    return bpy.context.scene


def setup_scene(width=1080, height=1920, fps=30, duration=8.0, samples=16,
                sky="sky", sun_dir=(-0.4, 0.3, -1.0), line_px=3.0, palette=None):
    s = bpy.context.scene
    s.render.engine = _engine_id()
    s.render.resolution_x = width
    s.render.resolution_y = height
    s.render.resolution_percentage = 100
    s.render.fps = fps
    s.frame_start = 1
    s.frame_end = int(round(duration * fps))
    s.view_settings.view_transform = "Standard"
    s.view_settings.look = "None"
    if hasattr(s, "eevee"):
        s.eevee.taa_render_samples = samples
        if hasattr(s.eevee, "use_shadows"):
            s.eevee.use_shadows = True
    # world
    w = bpy.data.worlds.new("World")
    s.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = rgb(sky, palette)
    bg.inputs["Strength"].default_value = 1.0
    # sun
    sun = bpy.data.lights.new("Sun", "SUN")
    sun.energy = 3.0
    sun.angle = math.radians(3)
    sun.use_shadow = True
    so = bpy.data.objects.new("Sun", sun)
    s.collection.objects.link(so)
    so.rotation_euler = Vector(sun_dir).to_track_quat("-Z", "Y").to_euler()
    # freestyle outline
    s.render.use_freestyle = True
    s.render.line_thickness_mode = "ABSOLUTE"
    s.render.line_thickness = line_px
    vl = bpy.context.view_layer
    fs = vl.freestyle_settings
    fs.crease_angle = math.radians(140)
    for ls in list(fs.linesets):
        fs.linesets.remove(ls)
    ls = fs.linesets.new("Outline")
    ls.select_silhouette = True
    ls.select_crease = True
    ls.select_border = True
    ls.select_contour = False
    ls.linestyle.color = (0.05, 0.05, 0.05)
    ls.linestyle.thickness = line_px
    return s


# ---------------------------------------------------------------- materials

def _sock(node, identifier):
    for sk in list(node.inputs) + list(node.outputs):
        if sk.identifier == identifier:
            return sk
    raise KeyError(identifier)


SHADOW_TINT = (0.74, 0.72, 0.88)  # cool, saturated: grey shadows read as dirty


def toon_material(name, color, shade=None, palette=None, grid=None):
    """Flat cel shader: base colour, one darker shadow band, optional cell grid.

    grid = {"cols": 6, "rows": 10, "line": "panel_cell", "width": 0.06}
    """
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    diff = nt.nodes.new("ShaderNodeBsdfDiffuse")
    diff.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    tint = SHADOW_TINT if shade is None else ((shade, shade, shade) if isinstance(shade, (int, float)) else tuple(shade))
    ramp.color_ramp.elements[0].color = (tint[0], tint[1], tint[2], 1)
    ramp.color_ramp.elements[1].position = 0.45
    ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs["Factor"].default_value = 1.0
    emis = nt.nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 1.0
    glow = nt.nodes.new("ShaderNodeEmission")
    glow.name = "Glow"
    glow.inputs["Color"].default_value = (1.0, 0.9, 0.5, 1)
    glow.inputs["Strength"].default_value = 0.0
    add = nt.nodes.new("ShaderNodeAddShader")

    if grid:
        brick = nt.nodes.new("ShaderNodeTexBrick")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        brick.offset = 0.0
        brick.inputs["Scale"].default_value = 1.0
        brick.inputs["Mortar Size"].default_value = grid.get("width", 0.06) / grid.get("cols", 6)
        brick.inputs["Brick Width"].default_value = 1.0 / grid.get("cols", 6)
        brick.inputs["Row Height"].default_value = 1.0 / grid.get("rows", 10)
        brick.inputs["Color1"].default_value = rgb(color, palette)
        brick.inputs["Color2"].default_value = rgb(color, palette)
        brick.inputs["Mortar"].default_value = rgb(grid.get("line", "panel_cell"), palette)
        nt.links.new(tc.outputs["Generated"], brick.inputs["Vector"])
        base_out = brick.outputs["Color"]
    else:
        col = nt.nodes.new("ShaderNodeRGB")
        col.name = "BaseColor"
        col.outputs[0].default_value = rgb(color, palette)
        base_out = col.outputs[0]

    nt.links.new(diff.outputs[0], s2r.inputs[0])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], _sock(mix, "A_Color"))
    nt.links.new(base_out, _sock(mix, "B_Color"))
    nt.links.new(base_out, glow.inputs["Color"])
    nt.links.new(_sock(mix, "Result_Color"), emis.inputs["Color"])
    nt.links.new(emis.outputs[0], add.inputs[0])
    nt.links.new(glow.outputs[0], add.inputs[1])
    nt.links.new(add.outputs[0], out.inputs["Surface"])
    return m


def dash_material(name, base="cable", dash="dash", period=0.25, duty=0.3, palette=None):
    """Cable material with yellow dashes along the curve. Mapping X is keyframed by anim_flow."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.name = "Flow"
    wave = nt.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.wave_profile = "SAW"
    wave.inputs["Scale"].default_value = 1.0 / period
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    ramp.color_ramp.elements[0].color = rgb(base, palette)
    ramp.color_ramp.elements[1].position = 1.0 - duty
    ramp.color_ramp.elements[1].color = rgb(dash, palette)
    emis = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], wave.inputs["Vector"])
    nt.links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], emis.inputs["Color"])
    nt.links.new(emis.outputs[0], out.inputs["Surface"])
    return m


def _assign(obj, mat):
    obj.data.materials.clear()
    obj.data.materials.append(mat)


# ---------------------------------------------------------------- prefabs

def _link(obj, name):
    obj.name = name
    return obj


def box(name, size=(1, 1, 1), pos=(0, 0, 0), rot=(0, 0, 0), color="concrete", palette=None, grid=None, shade=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=pos)
    o = bpy.context.active_object
    o.scale = Vector(size)
    o.rotation_euler = [math.radians(a) for a in rot]
    _assign(o, toon_material(name + "_mat", color, shade=shade, palette=palette, grid=grid))
    return _link(o, name)


def plane(name, size=(20, 20), pos=(0, 0, 0), color="grass", palette=None):
    bpy.ops.mesh.primitive_plane_add(size=1.0, location=pos)
    o = bpy.context.active_object
    o.scale = (size[0], size[1], 1)
    _assign(o, toon_material(name + "_mat", color, palette=palette))
    return _link(o, name)


def cylinder(name, radius=0.5, height=1.0, pos=(0, 0, 0), rot=(0, 0, 0), color="tank", palette=None, verts=24):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius, depth=height, location=pos)
    o = bpy.context.active_object
    bpy.ops.object.shade_smooth()
    o.rotation_euler = [math.radians(a) for a in rot]
    _assign(o, toon_material(name + "_mat", color, palette=palette))
    return _link(o, name)


def sphere(name, radius=0.5, pos=(0, 0, 0), color="sun", palette=None, shade=None, smooth=True):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=pos)
    o = bpy.context.active_object
    if smooth:
        bpy.ops.object.shade_smooth()
    _assign(o, toon_material(name + "_mat", color, palette=palette, shade=shade))
    return _link(o, name)


def empty(name, pos=(0, 0, 0)):
    o = bpy.data.objects.new(name, None)
    bpy.context.scene.collection.objects.link(o)
    o.location = pos
    return o


def panel(name, pos=(0, 0, 0), size=(1.0, 1.65), tilt=15, rot_z=0, color="panel", frame="frame", palette=None, grid=None):
    """Solar panel: white frame box + blue cell box, tilted around X. Returns parent empty."""
    grid = grid or {"cols": 6, "rows": 10, "line": "panel_cell", "width": 0.05}
    root = empty(name, pos)
    root.rotation_euler = (math.radians(tilt), 0, math.radians(rot_z))
    f = box(name + "_frame", size=(size[0] + 0.04, size[1] + 0.04, 0.05), pos=(0, 0, 0), color=frame, palette=palette)
    c = box(name + "_cells", size=(size[0], size[1], 0.03), pos=(0, 0, 0.03), color=color, palette=palette, grid=grid)
    for o in (f, c):
        o.parent = root
    return root


def panel_row(name, count=6, pos=(0, 0, 0), size=(1.0, 1.65), tilt=15, gap=0.06, axis="x", rot_z=0, palette=None, **kw):
    """Row of panels along local axis. Returns parent empty with children in order."""
    root = empty(name, pos)
    root.rotation_euler = (0, 0, math.radians(rot_z))
    step = (size[0] if axis == "x" else size[1]) + gap
    for i in range(count):
        off = (i * step, 0, 0) if axis == "x" else (0, i * step, 0)
        p = panel(f"{name}_{i}", pos=off, size=size, tilt=tilt, palette=palette, **kw)
        p.parent = root
    return root


def cable(name, points, radius=0.04, color="cable", dash="dash", period=0.25, palette=None, smooth=True):
    """Cable along points as bevelled curve. Material has moving dashes (see anim_flow)."""
    cu = bpy.data.curves.new(name + "_curve", "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER" if smooth else "POLY")
    n = len(points)
    if smooth:
        sp.bezier_points.add(n - 1)
        for bp, p in zip(sp.bezier_points, points):
            bp.co = Vector(p)
            bp.handle_left_type = bp.handle_right_type = "AUTO"
    else:
        sp.points.add(n - 1)
        for pt, p in zip(sp.points, points):
            pt.co = (p[0], p[1], p[2], 1.0)
    o = bpy.data.objects.new(name, cu)
    bpy.context.scene.collection.objects.link(o)
    length = sum((Vector(points[i + 1]) - Vector(points[i])).length for i in range(n - 1))
    m = dash_material(name + "_mat", base=color, dash=dash, period=period / max(length, 1e-3), palette=palette)
    o.data.materials.append(m)
    o["cable_length"] = length
    return o


def device(name, size=(0.8, 0.25, 1.2), pos=(0, 0, 0), rot=(0, 0, 0), color="white", screen="green", palette=None):
    """Wall box (inverter / meter) with a small screen. Returns parent empty."""
    root = empty(name, pos)
    root.rotation_euler = [math.radians(a) for a in rot]
    body = box(name + "_body", size=size, pos=(0, 0, 0), color=color, palette=palette)
    scr = box(name + "_screen", size=(size[0] * 0.45, 0.02, size[2] * 0.2), pos=(0, -size[1] / 2 - 0.005, size[2] * 0.25), color=screen, palette=palette)
    for o in (body, scr):
        o.parent = root
    return root


def car(name, pos=(0, 0, 0), rot_z=0, color="red", length=4.2, palette=None):
    """Low-poly car: body, cabin, four wheels. Faces -Y (nose toward the camera by default)."""
    root = empty(name, pos)
    root.rotation_euler = (0, 0, math.radians(rot_z))
    w = length * 0.43
    parts = [
        box(name + "_body", size=(w, length, 0.62), pos=(0, 0, 0.62), color=color, palette=palette),
        box(name + "_cabin", size=(w * 0.88, length * 0.5, 0.55), pos=(0, 0.15 * length, 1.18), color=color, palette=palette),
        box(name + "_glass", size=(w * 0.9, length * 0.52, 0.3), pos=(0, 0.15 * length, 1.22), color="sky", palette=palette),
        box(name + "_light_l", size=(0.25, 0.08, 0.12), pos=(-w * 0.32, -length / 2 - 0.02, 0.7), color="dash", palette=palette),
        box(name + "_light_r", size=(0.25, 0.08, 0.12), pos=(w * 0.32, -length / 2 - 0.02, 0.7), color="dash", palette=palette),
    ]
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(cylinder(name + f"_wheel{sx}{sy}", radius=0.34, height=0.26, pos=(sx * w * 0.5, sy * length * 0.3, 0.34),
                                  rot=(0, 90, 0), color="black", palette=palette, verts=20))
    for o in parts:
        o.parent = root
    return root


def charger(name, pos=(0, 0, 0), rot_z=0, color="white", screen="green", palette=None):
    """Level 2 pedestal charger: post, head with screen, short hose. Screen faces -Y."""
    root = empty(name, pos)
    root.rotation_euler = (0, 0, math.radians(rot_z))
    parts = [
        box(name + "_base", size=(0.5, 0.4, 0.08), pos=(0, 0, 0.04), color="metal", palette=palette),
        box(name + "_post", size=(0.28, 0.22, 0.9), pos=(0, 0, 0.5), color="metal", palette=palette),
        box(name + "_head", size=(0.42, 0.3, 0.75), pos=(0, 0, 1.3), color=color, palette=palette),
        box(name + "_screen", size=(0.26, 0.02, 0.18), pos=(0, -0.155, 1.45), color=screen, palette=palette),
        box(name + "_plug", size=(0.1, 0.08, 0.2), pos=(0.24, -0.05, 1.15), color="black", palette=palette),
        cable(name + "_hose", [(0.26, -0.05, 1.05), (0.34, -0.2, 0.6), (0.3, -0.25, 0.1)], radius=0.025, color="black", dash="black", palette=palette),
    ]
    for o in parts:
        o.parent = root
    return root


def cloud(name, pos=(0, 0, 8), scale=1.0, palette=None):
    """Flat cartoon cloud: three merged spheres, almost no shading."""
    root = empty(name, pos)
    tint = (0.93, 0.95, 1.0)
    parts = [
        sphere(name + "_a", radius=1.1 * scale, pos=(0, 0, 0), color="white", palette=palette, shade=tint),
        sphere(name + "_b", radius=0.85 * scale, pos=(-1.2 * scale, 0, -0.15 * scale), color="white", palette=palette, shade=tint),
        sphere(name + "_c", radius=0.9 * scale, pos=(1.2 * scale, 0, -0.1 * scale), color="white", palette=palette, shade=tint),
    ]
    for o in parts:
        o.parent = root
    return root


def tree(name, pos=(0, 0, 0), scale=1.0, color="green", palette=None):
    root = empty(name, pos)
    parts = [
        cylinder(name + "_trunk", radius=0.15 * scale, height=1.4 * scale, pos=(0, 0, 0.7 * scale), color="wood", palette=palette, verts=12),
        sphere(name + "_top", radius=1.1 * scale, pos=(0, 0, 2.1 * scale), color=color, palette=palette),
        sphere(name + "_top2", radius=0.8 * scale, pos=(0.6 * scale, 0.2 * scale, 2.7 * scale), color=color, palette=palette),
    ]
    for o in parts:
        o.parent = root
    return root


def transformer(name, pos=(0, 0, 0), size=(2.0, 1.5, 1.8), rot_z=0, color="metal", palette=None):
    """Pad-mounted transformer: cabinet, cooling fins on the back, base plate, warning plate. Front is -Y."""
    root = empty(name, pos)
    root.rotation_euler = (0, 0, math.radians(rot_z))
    w, d, h = size
    parts = [
        box(name + "_base", size=(w + 0.3, d + 0.3, 0.12), pos=(0, 0, 0.06), color="concrete", palette=palette),
        box(name + "_body", size=(w, d, h), pos=(0, 0, 0.12 + h / 2), color=color, palette=palette),
        box(name + "_lid", size=(w + 0.1, d + 0.1, 0.1), pos=(0, 0, 0.12 + h + 0.05), color=color, palette=palette),
        box(name + "_plate", size=(w * 0.35, 0.03, h * 0.18), pos=(-w * 0.22, -d / 2 - 0.015, 0.12 + h * 0.62), color="dash", palette=palette),
        box(name + "_door", size=(w * 0.3, 0.02, h * 0.55), pos=(w * 0.25, -d / 2 - 0.01, 0.12 + h * 0.4), color="frame", palette=palette),
    ]
    n = 5
    for i in range(n):
        x = -w / 2 + (i + 0.5) * w / n
        parts.append(box(name + f"_fin{i}", size=(w / n * 0.55, 0.35, h * 0.7), pos=(x, d / 2 + 0.17, 0.12 + h * 0.45), color=color, palette=palette))
    for o in parts:
        o.parent = root
    return root


def pole(name, pos=(0, 0, 0), height=6.0, palette=None):
    """Utility / light pole with a small head."""
    root = empty(name, pos)
    parts = [
        cylinder(name + "_post", radius=0.1, height=height, pos=(0, 0, height / 2), color="metal", palette=palette, verts=12),
        box(name + "_head", size=(0.9, 0.3, 0.2), pos=(0.3, 0, height), color="metal", palette=palette),
    ]
    for o in parts:
        o.parent = root
    return root


def import_model(name, path, pos=(0, 0, 0), scale=1.0, rot=(0, 0, 0)):
    """Import .glb/.gltf/.obj/.fbx as a group under an empty."""
    before = set(bpy.data.objects)
    low = path.lower()
    if low.endswith((".glb", ".gltf")):
        bpy.ops.import_scene.gltf(filepath=path)
    elif low.endswith(".obj"):
        bpy.ops.wm.obj_import(filepath=path)
    elif low.endswith(".fbx"):
        bpy.ops.import_scene.fbx(filepath=path)
    else:
        raise ValueError("unsupported model: " + path)
    new = [o for o in bpy.data.objects if o not in before and o.parent is None]
    root = empty(name, pos)
    root.scale = (scale, scale, scale)
    root.rotation_euler = [math.radians(a) for a in rot]
    for o in new:
        o.parent = root
    return root



def _fcurves(id_data):
    """All fcurves animating id_data (Blender 4.x legacy and 5.x slotted actions)."""
    ad = id_data.animation_data
    if not ad or not ad.action:
        return []
    act = ad.action
    if hasattr(act, "fcurves"):
        return list(act.fcurves)
    out = []
    for layer in act.layers:
        for strip in layer.strips:
            for cb in strip.channelbags:
                out.extend(cb.fcurves)
    return out


# ---------------------------------------------------------------- camera

def camera(lens=35):
    cd = bpy.data.cameras.new("Camera")
    cd.lens = lens
    cd.clip_end = 500
    cam = bpy.data.objects.new("Camera", cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    tgt = empty("CamTarget")
    con = cam.constraints.new("TRACK_TO")
    con.target = tgt
    con.track_axis = "TRACK_NEGATIVE_Z"
    con.up_axis = "UP_Y"
    return cam, tgt


def _f(t, fps):
    return int(round(t * fps)) + 1


def _orbit(spec, angle):
    c = Vector(spec.get("center", (0, 0, 0)))
    r = spec.get("radius", 12.0)
    h = spec.get("height", 7.0)
    a = math.radians(angle)
    return (c.x + r * math.cos(a), c.y + r * math.sin(a), c.z + h), tuple(c)


def shots(cam, tgt, shot_list, fps, lens_default=35):
    """shot = {t0, t1, from:{pos,look}, to:{pos,look}} or {t0,t1, orbit:{center,radius,height,angle_from,angle_to}}, optional lens."""
    for i, sh in enumerate(shot_list):
        f0, f1 = _f(sh["t0"], fps), _f(sh["t1"], fps)
        if "orbit" in sh:
            ob = sh["orbit"]
            p0, l0 = _orbit(ob, ob.get("angle_from", -60))
            p1, l1 = _orbit(ob, ob.get("angle_to", -30))
        else:
            p0, l0 = sh["from"]["pos"], sh["from"].get("look", (0, 0, 0))
            p1, l1 = sh["to"]["pos"], sh["to"].get("look", l0)
        lens = sh.get("lens", lens_default)
        for f, p, l in ((f0, p0, l0), (f1, p1, l1)):
            cam.location = p
            cam.keyframe_insert("location", frame=f)
            tgt.location = l
            tgt.keyframe_insert("location", frame=f)
            cam.data.lens = lens
            cam.data.keyframe_insert("lens", frame=f)
        # hard cut at the end of each shot: hold until next shot's first frame
        if i < len(shot_list) - 1:
            for ob in (cam, tgt):
                for fc in _fcurves(ob):
                    for kp in fc.keyframe_points:
                        if abs(kp.co.x - f1) < 0.5:
                            kp.interpolation = "CONSTANT"
    ease = ("SINE", "EASE_IN_OUT")
    for ob in (cam, tgt):
        for fc in _fcurves(ob):
            for kp in fc.keyframe_points:
                if kp.interpolation != "CONSTANT":
                    kp.interpolation, kp.easing = ease


# ---------------------------------------------------------------- animation

def _targets(obj, stagger):
    kids = [c for c in obj.children] if obj.type == "EMPTY" and obj.children and stagger else [obj]
    kids.sort(key=lambda o: o.name)
    return kids


def _set_interp(obj, kind="BACK", easing="EASE_OUT", path=None):
    for fc in _fcurves(obj):
        if path and fc.data_path != path:
            continue
        for kp in fc.keyframe_points:
            kp.interpolation = kind
            kp.easing = easing


def _hide_until(obj, f):
    for o in [obj] + list(obj.children_recursive):
        o.hide_render = True
        o.hide_viewport = True
        o.keyframe_insert("hide_render", frame=1)
        o.keyframe_insert("hide_viewport", frame=1)
        o.hide_render = False
        o.hide_viewport = False
        o.keyframe_insert("hide_render", frame=f)
        o.keyframe_insert("hide_viewport", frame=f)


def anim_drop_in(obj, t, fps, dur=0.5, height=3.0, stagger=0.12):
    for i, o in enumerate(_targets(obj, stagger)):
        f0 = _f(t + i * stagger, fps)
        f1 = _f(t + i * stagger + dur, fps)
        _hide_until(o, f0)
        base = o.location.copy()
        o.location = base + Vector((0, 0, height))
        o.keyframe_insert("location", frame=f0)
        o.location = base
        o.keyframe_insert("location", frame=f1)
        _set_interp(o, "BACK", "EASE_OUT", "location")


def anim_pop_in(obj, t, fps, dur=0.4, stagger=0.1):
    for i, o in enumerate(_targets(obj, stagger)):
        f0 = _f(t + i * stagger, fps)
        f1 = _f(t + i * stagger + dur, fps)
        _hide_until(o, f0)
        base = o.scale.copy()
        o.scale = (0.001, 0.001, 0.001)
        o.keyframe_insert("scale", frame=f0)
        o.scale = base
        o.keyframe_insert("scale", frame=f1)
        _set_interp(o, "BACK", "EASE_OUT", "scale")


def anim_slide_in(obj, t, fps, dur=0.5, offset=(-4, 0, 0), stagger=0.1):
    for i, o in enumerate(_targets(obj, stagger)):
        f0 = _f(t + i * stagger, fps)
        f1 = _f(t + i * stagger + dur, fps)
        _hide_until(o, f0)
        base = o.location.copy()
        o.location = base + Vector(offset)
        o.keyframe_insert("location", frame=f0)
        o.location = base
        o.keyframe_insert("location", frame=f1)
        _set_interp(o, "CUBIC", "EASE_OUT", "location")


def anim_hide(obj, t, fps):
    f = _f(t, fps)
    for o in [obj] + list(obj.children_recursive):
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=f - 1)
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=f)


def anim_show(obj, t, fps):
    f = _f(t, fps)
    for o in [obj] + list(obj.children_recursive):
        o.hide_render = True
        o.keyframe_insert("hide_render", frame=f - 1)
        o.hide_render = False
        o.keyframe_insert("hide_render", frame=f)


def anim_move(obj, t, fps, dur=1.0, to=None, by=None, rot_by=None):
    f0, f1 = _f(t, fps), _f(t + dur, fps)
    obj.keyframe_insert("location", frame=f0)
    obj.keyframe_insert("rotation_euler", frame=f0)
    if to is not None:
        obj.location = to
    if by is not None:
        obj.location = obj.location + Vector(by)
    if rot_by is not None:
        obj.rotation_euler = [a + math.radians(b) for a, b in zip(obj.rotation_euler, rot_by)]
    obj.keyframe_insert("location", frame=f1)
    obj.keyframe_insert("rotation_euler", frame=f1)


def _glow_nodes(obj):
    out = []
    for o in [obj] + list(obj.children_recursive):
        if o.type not in ("MESH", "CURVE"):
            continue
        for m in o.data.materials:
            if m and m.node_tree and "Glow" in m.node_tree.nodes:
                out.append(m.node_tree.nodes["Glow"].inputs["Strength"])
    return out


def anim_pulse(obj, t, fps, dur=1.0, strength=0.6, times=2):
    """Emission flash on all toon materials under obj."""
    socks = _glow_nodes(obj)
    step = dur / (times * 2)
    for s in socks:
        s.default_value = 0.0
        s.keyframe_insert("default_value", frame=_f(t, fps))
        for k in range(times):
            s.default_value = strength
            s.keyframe_insert("default_value", frame=_f(t + (2 * k + 1) * step, fps))
            s.default_value = 0.0
            s.keyframe_insert("default_value", frame=_f(t + (2 * k + 2) * step, fps))


def anim_glow(obj, t, fps, dur=0.3, strength=0.35, off_at=None):
    socks = _glow_nodes(obj)
    for s in socks:
        s.default_value = 0.0
        s.keyframe_insert("default_value", frame=_f(t, fps))
        s.default_value = strength
        s.keyframe_insert("default_value", frame=_f(t + dur, fps))
        if off_at is not None:
            s.keyframe_insert("default_value", frame=_f(off_at, fps))
            s.default_value = 0.0
            s.keyframe_insert("default_value", frame=_f(off_at + dur, fps))


def anim_flow(obj, t, fps, dur=None, speed=1.0, stop_at=None):
    """Move cable dashes along the curve. speed in metres per second. stop_at freezes them."""
    mp = obj.data.materials[0].node_tree.nodes["Flow"]
    loc = mp.inputs["Location"]
    length = max(obj.get("cable_length", 1.0), 1e-3)
    end = stop_at if stop_at is not None else (t + dur if dur else bpy.context.scene.frame_end / fps)
    loc.default_value = (0, 0, 0)
    loc.keyframe_insert("default_value", frame=_f(t, fps))
    loc.default_value = (-(end - t) * speed / length, 0, 0)
    loc.keyframe_insert("default_value", frame=_f(end, fps))
    nt = obj.data.materials[0].node_tree
    for fc in _fcurves(nt):
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"


def anim_draw(obj, t, fps, dur=0.8):
    """Cable grows along its path (bevel_factor_end 0 -> 1)."""
    f0, f1 = _f(t, fps), _f(t + dur, fps)
    _hide_until(obj, f0)
    cu = obj.data
    cu.bevel_factor_end = 0.0
    cu.keyframe_insert("bevel_factor_end", frame=f0)
    cu.bevel_factor_end = 1.0
    cu.keyframe_insert("bevel_factor_end", frame=f1)
    for fc in _fcurves(cu):
        for kp in fc.keyframe_points:
            kp.interpolation, kp.easing = "CUBIC", "EASE_IN_OUT"


def anim_color(obj, t, fps, color, dur=0.2, palette=None):
    """Swap base colour of a plain toon material (no grid)."""
    for o in [obj] + list(obj.children_recursive):
        if o.type != "MESH":
            continue
        for m in o.data.materials:
            n = m.node_tree.nodes.get("BaseColor") if m and m.node_tree else None
            if not n:
                continue
            sk = n.outputs[0]
            sk.keyframe_insert("default_value", frame=_f(t, fps))
            sk.default_value = rgb(color, palette)
            sk.keyframe_insert("default_value", frame=_f(t + dur, fps))


ANIMS = {
    "drop_in": anim_drop_in,
    "pop_in": anim_pop_in,
    "slide_in": anim_slide_in,
    "hide": anim_hide,
    "show": anim_show,
    "move": anim_move,
    "pulse": anim_pulse,
    "glow": anim_glow,
    "flow": anim_flow,
    "draw": anim_draw,
    "color": anim_color,
}

PREFABS = {
    "box": box,
    "plane": plane,
    "cylinder": cylinder,
    "sphere": sphere,
    "panel": panel,
    "panel_row": panel_row,
    "cable": cable,
    "device": device,
    "car": car,
    "charger": charger,
    "cloud": cloud,
    "tree": tree,
    "pole": pole,
    "transformer": transformer,
    "model": import_model,
    "empty": empty,
}
