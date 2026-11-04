#!/usr/bin/env python3
"""Blender MCP server --- Streamable HTTP transport.

Exposes ~35 tools that control a headless Blender process via a localhost
socket bridge (blender_bridge.py). Auth: optional Bearer token via
BLENDER_MCP_TOKEN (set in production). /health is always open.
"""

import datetime
import json
import os
import shutil
import socket
import struct
import threading
import traceback

from mcp.server.fastmcp import FastMCP

try:
    from mcp.server.fastmcp import Image as _Image
except Exception:  # pragma: no cover
    try:
        from mcp.server.fastmcp.utilities.types import Image as _Image
    except Exception:
        _Image = None

DATA_DIR = os.environ.get("DATA_DIR", "/data")
BRIDGE_HOST = os.environ.get("BLENDER_BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.environ.get("BLENDER_BRIDGE_PORT", "9876"))
TOKEN = os.environ.get("BLENDER_MCP_TOKEN") or None
PORT = int(os.environ.get("PORT", "8000"))

SUBDIRS = ["projects", "renders", "assets", "textures", "exports", "logs", "backups"]
for _d in SUBDIRS:
    os.makedirs(os.path.join(DATA_DIR, _d), exist_ok=True)

mcp = FastMCP(
    name="blender-mcp",
    instructions=(
        "Tools to control a headless Blender 4.5 LTS instance: scene info, primitives, "
        "collections, materials, lights, cameras, animation keyframes, render settings, "
        "rendering, saving/opening .blend files, import/export, file and log management. "
        "Rotation arguments are in DEGREES. All paths must live under /data."
    ),
    host="0.0.0.0",
    port=PORT,
    streamable_http_path="/mcp",
)

BRIDGE_LOCK = threading.Lock()


# --------------------------------------------------------------------------- helpers

def _safe_path(path: str, must_exist: bool = False) -> str:
    """Resolve path and ensure it lives under DATA_DIR."""
    if not path:
        raise ValueError("path is required")
    p = os.path.realpath(path if os.path.isabs(path) else os.path.join(DATA_DIR, path))
    root = os.path.realpath(DATA_DIR)
    if p != root and not p.startswith(root + os.sep):
        raise ValueError(f"path must be under {DATA_DIR}: {path}")
    if must_exist and not os.path.exists(p):
        raise ValueError(f"path does not exist: {p}")
    return p


def _py(v):
    """Python literal for embedding in generated code."""
    return repr(v)


def _bridge_call(req: dict, timeout: float = 180.0) -> dict:
    payload = json.dumps(req).encode("utf-8")
    with BRIDGE_LOCK:
        s = socket.create_connection((BRIDGE_HOST, BRIDGE_PORT), timeout=timeout)
        try:
            s.settimeout(timeout)
            s.sendall(struct.pack(">I", len(payload)) + payload)
            header = b""
            while len(header) < 4:
                chunk = s.recv(4 - len(header))
                if not chunk:
                    raise ConnectionError("bridge closed connection")
                header += chunk
            (length,) = struct.unpack(">I", header)
            body = b""
            while len(body) < length:
                chunk = s.recv(min(1 << 16, length - len(body)))
                if not chunk:
                    raise ConnectionError("bridge closed connection mid-body")
                body += chunk
            return json.loads(body.decode("utf-8"))
        finally:
            try:
                s.close()
            except Exception:
                pass


def _run_bpy(code: str, timeout: float = 180.0):
    """Execute Python inside Blender; raise on error, else return _result."""
    resp = _bridge_call({"id": os.urandom(8).hex(), "type": "exec", "params": {"code": code}}, timeout=timeout)
    if resp.get("status") != "ok":
        raise RuntimeError(resp.get("message", "Blender error"))
    out = resp.get("result")
    stdout = (resp.get("stdout") or "").strip()
    if stdout:
        if isinstance(out, dict):
            out = {**out, "_stdout": stdout}
        elif out is None:
            out = {"_stdout": stdout}
    return out


def _hex_to_rgba(color) -> list:
    if isinstance(color, str):
        c = color.lstrip("#")
        if len(c) == 6:
            return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]
        if len(c) == 8:
            return [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4, 6)]
        raise ValueError("hex color must be #RRGGBB or #RRGGBBAA")
    vals = [float(v) for v in color]
    if len(vals) == 3:
        vals.append(1.0)
    if len(vals) != 4:
        raise ValueError("color must be #hex or [r,g,b(,a)]")
    return vals


def _ok(payload):
    return json.dumps(payload, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- info tools

@mcp.tool()
def health() -> str:
    """Liveness probe: bridge reachability, Blender version, data dir free space."""
    try:
        resp = _bridge_call({"id": "health", "type": "ping"}, timeout=10)
        pong = resp.get("result", resp)
    except Exception as exc:
        pong = {"pong": False, "error": str(exc)}
    usage = shutil.disk_usage(DATA_DIR)
    return _ok({
        "status": "ok" if pong.get("pong") else "degraded",
        "blender": pong,
        "data_dir": DATA_DIR,
        "disk_free_gb": round(usage.free / (1024 ** 3), 2),
        "disk_total_gb": round(usage.total / (1024 ** 3), 2),
        "subdirs": SUBDIRS,
    })


@mcp.tool()
def get_scene_info() -> str:
    """Summary of the current scene: objects, collections, materials, cameras,
    lights, render settings and frame range."""
    code = r"""
import bpy, json
scene = bpy.context.scene

def obj_entry(o):
    mats = [m.name for m in getattr(o.data, 'materials', [])] if hasattr(o.data, 'materials') else []
    return {
        'name': o.name, 'type': o.type,
        'location': list(o.location),
        'rotation_euler_deg': [round(a * 57.29578, 3) for a in o.rotation_euler],
        'scale': list(o.scale),
        'visible': not o.hide_viewport,
        'collections': [c.name for c in o.users_collection],
        'materials': mats,
    }

eng = scene.render
info = {
    'blender_version': bpy.app.version_string,
    'scene': scene.name,
    'frame_current': scene.frame_current,
    'frame_start': scene.frame_start,
    'frame_end': scene.frame_end,
    'fps': scene.render.fps,
    'engine': scene.render.engine,
    'resolution_x': eng.resolution_x,
    'resolution_y': eng.resolution_y,
    'resolution_percentage': eng.resolution_percentage,
    'film_transparent': eng.film_transparent,
    'cycles_samples': getattr(getattr(scene, 'cycles', None), 'samples', None),
    'active_camera': scene.camera.name if scene.camera else None,
    'collections': [c.name for c in bpy.data.collections],
    'objects': [obj_entry(o) for o in bpy.data.objects],
    'object_count': len(bpy.data.objects),
    'materials': [m.name for m in bpy.data.materials],
    'cameras': [o.name for o in bpy.data.objects if o.type == 'CAMERA'],
    'lights': [{'name': o.name, 'type': o.data.type, 'energy': o.data.energy} for o in bpy.data.objects if o.type == 'LIGHT'],
}
_result = info
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def get_object_info(name: str) -> str:
    """Detailed info for one object (transform, data, modifiers, materials)."""
    code = f"""
import bpy
o = bpy.data.objects.get({_py(name)})
if o is None:
    raise ValueError('object not found: {name}')
_result = {{
    'name': o.name, 'type': o.type,
    'location': list(o.location),
    'rotation_euler_deg': [round(a * 57.29578, 3) for a in o.rotation_euler],
    'scale': list(o.scale),
    'dimensions': list(o.dimensions),
    'collections': [c.name for c in o.users_collection],
    'modifiers': [{{'name': m.name, 'type': m.type}} for m in o.modifiers],
    'materials': [m.name for m in getattr(o.data, 'materials', [])] if hasattr(o.data, 'materials') else [],
    'vertices': len(o.data.vertices) if o.type == 'MESH' else None,
    'polygons': len(o.data.polygons) if o.type == 'MESH' else None,
    'visible': not o.hide_viewport,
}}
"""
    return _ok(_run_bpy(code))


# --------------------------------------------------------------------------- scene / projects

@mcp.tool()
def reset_scene() -> str:
    """Reset to an empty factory scene (does not delete files on disk)."""
    code = """
import bpy
bpy.ops.wm.read_homefile(use_empty=True)
_result = {'scene': bpy.context.scene.name, 'objects': len(bpy.data.objects)}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def new_project(name: str) -> str:
    """Create a project folder under /data/projects/<name>, reset the scene,
    and save an initial <name>.blend there."""
    safe = "".join(c if (c.isalnum() or c in "-_ ") else "_" for c in name).strip()
    if not safe:
        raise ValueError("invalid project name")
    proj = os.path.join(DATA_DIR, "projects", safe)
    os.makedirs(proj, exist_ok=True)
    blend = os.path.join(proj, f"{safe}.blend")
    code = f"""
import bpy
bpy.ops.wm.read_homefile(use_empty=True)
bpy.ops.wm.save_as_mainfile(filepath={_py(blend)})
_result = {{'project': {_py(safe)}, 'blend': {_py(blend)}}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def list_projects() -> str:
    """List all projects under /data/projects with their .blend files."""
    out = []
    base = os.path.join(DATA_DIR, "projects")
    for entry in sorted(os.listdir(base)):
        p = os.path.join(base, entry)
        if not os.path.isdir(p):
            continue
        blends = [f for f in os.listdir(p) if f.endswith(".blend")]
        out.append({
            "project": entry,
            "blend_files": blends,
            "path": p,
            "size_kb": round(sum(os.path.getsize(os.path.join(p, f)) for f in os.listdir(p)) / 1024, 1),
        })
    return _ok(out)


@mcp.tool()
def save_scene(project: str = "", name: str = "") -> str:
    """Save the current blend file. If a file would be overwritten, the old one is
    first copied to /data/backups/<stem>_<timestamp>.blend (never destroys work).
    With no arguments, saves over the current file (with backup)."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if project or name:
        proj = project or "default"
        fname = (name or proj) + ".blend"
        target = _safe_path(os.path.join("projects", proj, fname))
        os.makedirs(os.path.dirname(target), exist_ok=True)
    else:
        target = None  # save over current file
    backup_dir = os.path.join(DATA_DIR, "backups")
    code = f"""
import bpy, os, shutil, datetime
blend = bpy.data.filepath
target = {_py(target)}
if target:
    final = target
else:
    if not blend:
        final = os.path.join({_py(DATA_DIR)}, 'projects', 'default', 'scene.blend')
        os.makedirs(os.path.dirname(final), exist_ok=True)
    else:
        final = blend
if os.path.exists(final):
    stem = os.path.splitext(os.path.basename(final))[0]
    shutil.copy2(final, os.path.join({_py(backup_dir)}, f"{{stem}}_{ts}.blend"))
bpy.ops.wm.save_as_mainfile(filepath=final)
_result = {{'saved': final}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def open_blend(path: str) -> str:
    """Open a .blend file (must be under /data)."""
    p = _safe_path(path, must_exist=True)
    if not p.endswith(".blend"):
        raise ValueError("not a .blend file")
    code = f"""
import bpy
bpy.ops.wm.open_mainfile(filepath={_py(p)})
_result = {{'opened': {_py(p)}, 'objects': len(bpy.data.objects), 'scene': bpy.context.scene.name}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def backup_project(project: str) -> str:
    """Copy all .blend files of a project into /data/backups with a timestamp."""
    pdir = _safe_path(os.path.join("projects", project), must_exist=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    copied = []
    for f in os.listdir(pdir):
        if f.endswith(".blend"):
            dst = os.path.join(DATA_DIR, "backups", f"{project}_{f[:-6]}_{ts}.blend")
            shutil.copy2(os.path.join(pdir, f), dst)
            copied.append(dst)
    return _ok({"backed_up": copied})


# --------------------------------------------------------------------------- objects

_PRIMITIVES = {
    "CUBE": "bpy.ops.mesh.primitive_cube_add(size=%(size)s, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "UV_SPHERE": "bpy.ops.mesh.primitive_uv_sphere_add(radius=%(size)s/2, segments=32, ring_count=16, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "ICO_SPHERE": "bpy.ops.mesh.primitive_ico_sphere_add(radius=%(size)s/2, subdivisions=2, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "CYLINDER": "bpy.ops.mesh.primitive_cylinder_add(radius=%(size)s/2, depth=%(size)s, vertices=32, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "CONE": "bpy.ops.mesh.primitive_cone_add(radius1=%(size)s/2, depth=%(size)s, vertices=32, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "PLANE": "bpy.ops.mesh.primitive_plane_add(size=%(size)s, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "TORUS": "bpy.ops.mesh.primitive_torus_add(major_radius=%(size)s/2, minor_radius=%(size)s/6, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
    "MONKEY": "bpy.ops.mesh.primitive_monkey_add(size=%(size)s, location=%(loc)s, rotation=%(rot)s, scale=%(scale)s)",
}


@mcp.tool()
def create_primitive(primitive_type: str, name: str = "", size: float = 2.0,
                     location: list = None, rotation: list = None, scale: list = None,
                     collection: str = "") -> str:
    """Create a mesh primitive: CUBE, UV_SPHERE, ICO_SPHERE, CYLINDER, CONE,
    PLANE, TORUS, MONKEY. location/rotation/scale as [x,y,z]; rotation in DEGREES."""
    t = primitive_type.upper().replace("-", "_").replace(" ", "_")
    if t not in _PRIMITIVES:
        raise ValueError(f"unknown primitive: {primitive_type}. Use one of {list(_PRIMITIVES)}")
    loc = location or [0.0, 0.0, 0.0]
    scale = scale or [1.0, 1.0, 1.0]
    rot_deg = rotation or [0.0, 0.0, 0.0]
    import math
    rot_rad = [math.radians(float(a)) for a in rot_deg]
    col_code = ""
    if collection:
        col_code = f"""
col = bpy.data.collections.get({_py(collection)})
if col is None:
    col = bpy.data.collections.new({_py(collection)})
    bpy.context.scene.collection.children.link(col)
for c in list(bpy.context.active_object.users_collection):
    if c != col:
        c.objects.unlink(bpy.context.active_object)
col.objects.link(bpy.context.active_object)
"""
    code = f"""
import bpy, math
bpy.ops.object.select_all(action='DESELECT')
{_PRIMITIVES[t] % {'size': _py(float(size)), 'loc': _py([float(v) for v in loc]), 'rot': _py(rot_rad), 'scale': _py([float(v) for v in scale])}}
obj = bpy.context.active_object
{col_code}
if {_py(name)}:
    obj.name = {_py(name)}
_result = {{'name': obj.name, 'type': obj.type, 'location': list(obj.location)}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def create_collection(name: str) -> str:
    """Create a scene collection (idempotent)."""
    code = f"""
import bpy
col = bpy.data.collections.get({_py(name)})
if col is None:
    col = bpy.data.collections.new({_py(name)})
    bpy.context.scene.collection.children.link(col)
_result = {{'collection': col.name, 'created': True}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def list_collections() -> str:
    """List all collections and the objects in them."""
    code = """
import bpy
_result = [{'name': c.name, 'objects': [o.name for o in c.objects]} for c in bpy.data.collections]
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def move_to_collection(object_name: str, collection: str) -> str:
    """Move an object into a collection (created if missing)."""
    code = f"""
import bpy
obj = bpy.data.objects.get({_py(object_name)})
if obj is None:
    raise ValueError('object not found: {object_name}')
col = bpy.data.collections.get({_py(collection)})
if col is None:
    col = bpy.data.collections.new({_py(collection)})
    bpy.context.scene.collection.children.link(col)
for c in list(obj.users_collection):
    c.objects.unlink(obj)
col.objects.link(obj)
_result = {{'object': obj.name, 'collection': col.name}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def set_transform(object_name: str, location: list = None, rotation: list = None, scale: list = None) -> str:
    """Set absolute transform for an object. rotation in DEGREES."""
    import math
    lines = [f"o = bpy.data.objects.get({_py(object_name)})",
             f"if o is None: raise ValueError('object not found: {object_name}')"]
    if location is not None:
        lines.append(f"o.location = {_py([float(v) for v in location])}")
    if rotation is not None:
        lines.append(f"o.rotation_euler = {_py([math.radians(float(v)) for v in rotation])}")
    if scale is not None:
        lines.append(f"o.scale = {_py([float(v) for v in scale])}")
    lines.append("_result = {'name': o.name, 'location': list(o.location), 'scale': list(o.scale)}")
    return _ok(_run_bpy("import bpy\n" + "\n".join(lines)))


@mcp.tool()
def delete_object(name: str) -> str:
    """Delete an object by name."""
    code = f"""
import bpy
o = bpy.data.objects.get({_py(name)})
if o is None:
    raise ValueError('object not found: {name}')
bpy.data.objects.remove(o, do_unlink=True)
_result = {{'deleted': {_py(name)}}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def duplicate_object(name: str, new_name: str = "") -> str:
    """Duplicate an object (shares mesh data unless object is converted)."""
    rename = f"new.name = {_py(new_name)}\n" if new_name else ""
    code = f"""
import bpy
src = bpy.data.objects.get({_py(name)})
if src is None:
    raise ValueError('object not found: {name}')
new = src.copy()
if src.data:
    new.data = src.data.copy()
{rename}bpy.context.collection.objects.link(new)
_result = {{'name': new.name}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def add_modifier(object_name: str, modifier_type: str, settings: dict = None) -> str:
    """Add a modifier. modifier_type: SUBSURF, BEVEL, MIRROR, ARRAY, SOLIDIFY, DECIMATE.
    settings: e.g. {'levels': 2} for SUBSURF, {'width': 0.1} for BEVEL,
    {'use_axis': [True,False,False]} for MIRROR, {'count': 3, 'relative_offset_displace': [2,0,0]} for ARRAY."""
    mtype = modifier_type.upper()
    if mtype not in ("SUBSURF", "BEVEL", "MIRROR", "ARRAY", "SOLIDIFY", "DECIMATE", "WIREFRAME"):
        raise ValueError("unsupported modifier. Use SUBSURF, BEVEL, MIRROR, ARRAY, SOLIDIFY, DECIMATE, WIREFRAME")
    settings = settings or {}
    code = f"""
import bpy
o = bpy.data.objects.get({_py(object_name)})
if o is None:
    raise ValueError('object not found: {object_name}')
m = o.modifiers.new(name='{mtype}_MCP', type='{mtype}')
for k, v in {_py(settings)}.items():
    try:
        setattr(m, k, v)
    except Exception as exc:
        print('modifier setting skipped:', k, exc)
_result = {{'object': o.name, 'modifier': m.name, 'type': m.type}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def set_shade_smooth(object_name: str, smooth: bool = True) -> str:
    """Toggle smooth shading (auto smooth via geometry nodes not needed in 4.1+)."""
    code = f"""
import bpy
o = bpy.data.objects.get({_py(object_name)})
if o is None or o.type != 'MESH':
    raise ValueError('mesh object not found: {object_name}')
for p in o.data.polygons:
    p.use_smooth = {bool(smooth)}
_result = {{'object': o.name, 'smooth': {bool(smooth)}}}
"""
    return _ok(_run_bpy(code))


# --------------------------------------------------------------------------- materials

@mcp.tool()
def create_material(name: str, color: str = "#b0b0b0", metallic: float = 0.0,
                    roughness: float = 0.5, ior: float = 1.45, transmission: float = 0.0,
                    emission_color: str = "", emission_strength: float = 0.0,
                    assign_to: str = "") -> str:
    """Create a Principled BSDF material. color = '#RRGGBB' or [r,g,b,a].
    Optionally assign to an object via assign_to."""
    rgba = _hex_to_rgba(color)
    emis = _hex_to_rgba(emission_color) if emission_color else None
    # NOTE: keep the f-string expressions free of backslashes — the MCP server
    # runs on Python 3.11 (Debian bookworm), where PEP 701 (backslashes inside
    # f-string expressions) is a SyntaxError.
    assign_block = ""
    if assign_to:
        assign_block = (f"o = bpy.data.objects.get({_py(assign_to)})"
                        "\nif o and hasattr(o.data, 'materials'): o.data.materials.append(m)")
    code = f"""
import bpy
m = bpy.data.materials.get({_py(name)}) or bpy.data.materials.new({_py(name)})
m.use_nodes = True
bsdf = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
def set_in(keys, value):
    for k in keys:
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = value
            return k
    return None
set_in(['Base Color'], {_py(rgba)})
set_in(['Metallic'], {float(metallic)})
set_in(['Roughness'], {float(roughness)})
set_in(['IOR'], {float(ior)})
set_in(['Transmission Weight', 'Transmission'], {float(transmission)})
{f"set_in(['Emission Color', 'Emission'], {_py(emis)})" if emis else ""}
{f"set_in(['Emission Strength'], {float(emission_strength)})" if emission_strength else ""}
{assign_block}
_result = {{'material': m.name, 'assigned_to': {_py(assign_to) if assign_to else None}}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def assign_material(object_name: str, material: str) -> str:
    """Assign an existing material to an object (creating an empty slot path)."""
    code = f"""
import bpy
o = bpy.data.objects.get({_py(object_name)})
m = bpy.data.materials.get({_py(material)})
if o is None:
    raise ValueError('object not found: {object_name}')
if m is None:
    raise ValueError('material not found: {material}')
if not hasattr(o.data, 'materials'):
    raise ValueError('object has no material slots (not a mesh/curve)')
o.data.materials.append(m)
_result = {{'object': o.name, 'material': m.name, 'slots': len(o.data.materials)}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def list_materials() -> str:
    """List materials with their key Principled BSDF values."""
    code = """
import bpy
out = []
for m in bpy.data.materials:
    entry = {'name': m.name, 'use_nodes': m.use_nodes}
    if m.use_nodes and m.node_tree:
        for n in m.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                def inp(k):
                    return list(n.inputs[k].default_value) if k in n.inputs else None
                entry.update({'base_color': inp('Base Color'), 'metallic': inp('Metallic'),
                              'roughness': inp('Roughness'), 'ior': inp('IOR')})
    out.append(entry)
_result = out
"""
    return _ok(_run_bpy(code))


# --------------------------------------------------------------------------- lights / cameras / world

@mcp.tool()
def add_light(light_type: str, name: str = "", location: list = None, rotation: list = None,
              energy: float = 1000.0, color: str = "#ffffff") -> str:
    """Add a light. light_type: POINT, SUN, SPOT, AREA. rotation in DEGREES.
    energy in Watts (POINT/SPOT/AREA) or irradiance (SUN). color '#RRGGBB'."""
    lt = light_type.upper()
    if lt not in ("POINT", "SUN", "SPOT", "AREA"):
        raise ValueError("light_type must be POINT, SUN, SPOT or AREA")
    loc = location or [0.0, 0.0, 5.0]
    import math
    rot = [math.radians(float(v)) for v in (rotation or [0.0, 0.0, 0.0])]
    rgba = _hex_to_rgba(color)[:3]
    code = f"""
import bpy, math
bpy.ops.object.light_add(type={_py(lt)}, location={_py([float(v) for v in loc])}, rotation={_py(rot)})
o = bpy.context.active_object
if {_py(name)}:
    o.name = {_py(name)}
o.data.energy = {float(energy)}
o.data.color = {_py(rgba)}
_result = {{'name': o.name, 'type': o.data.type, 'energy': o.data.energy}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def add_camera(name: str = "Camera", location: list = None, look_at: list = None,
               rotation: list = None, lens: float = 50.0) -> str:
    """Add a camera and make it active. Either pass look_at=[x,y,z] to aim at a
    target, or an explicit rotation (DEGREES). lens in mm."""
    loc = location or [7.0, -7.0, 5.0]
    import math
    if look_at is not None:
        target = [float(v) for v in look_at]
        aim = f"""
import mathutils
direction = (mathutils.Vector({_py(target)}) - cam.location)
cam.rotation_euler = direction.to_track_quat('-Z', 'Y').to_euler()
"""
    else:
        rot = [math.radians(float(v)) for v in (rotation or [63.0, 0.0, 46.0])]
        aim = f"cam.rotation_euler = {_py(rot)}\n"
    code = f"""
import bpy, math
bpy.ops.object.camera_add(location={_py([float(v) for v in loc])})
cam = bpy.context.active_object
cam.name = {_py(name)}
cam.data.lens = {float(lens)}
{aim}bpy.context.scene.camera = cam
_result = {{'name': cam.name, 'lens': cam.data.lens, 'location': list(cam.location),
            'rotation_deg': [round(a * 57.29578, 2) for a in cam.rotation_euler]}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def set_active_camera(name: str) -> str:
    """Make an existing camera object the scene's active camera."""
    code = f"""
import bpy
cam = bpy.data.objects.get({_py(name)})
if cam is None or cam.type != 'CAMERA':
    raise ValueError('camera not found: {name}')
bpy.context.scene.camera = cam
_result = {{'active_camera': cam.name}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def set_world(color: str = "#808080", strength: float = 1.0) -> str:
    """Set the world background (flat color) --- works as ambient light for Cycles."""
    rgb = _hex_to_rgba(color)[:3]
    code = f"""
import bpy
world = bpy.data.worlds.get('MCP_World') or bpy.data.worlds.new('MCP_World')
bpy.context.scene.world = world
world.use_nodes = True
bg = next((n for n in world.node_tree.nodes if n.type == 'BACKGROUND'), None)
bg.inputs['Color'].default_value = ({rgb[0]}, {rgb[1]}, {rgb[2]}, 1.0)
bg.inputs['Strength'].default_value = {float(strength)}
_result = {{'world': world.name, 'strength': bg.inputs['Strength'].default_value}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def world_hdri(image_path: str, strength: float = 1.0) -> str:
    """Use an HDR/EXR image under /data as the world environment texture."""
    p = _safe_path(image_path, must_exist=True)
    code = f"""
import bpy
world = bpy.data.worlds.get('MCP_World') or bpy.data.worlds.new('MCP_World')
bpy.context.scene.world = world
world.use_nodes = True
nt = world.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
bg = nt.nodes.new('ShaderNodeBackground')
tex = nt.nodes.new('ShaderNodeTexEnvironment')
tex.image = bpy.data.images.load({_py(p)})
bg.inputs['Strength'].default_value = {float(strength)}
out = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(tex.outputs['Color'], bg.inputs['Color'])
nt.links.new(bg.outputs['Background'], out.inputs['Surface'])
_result = {{'world': world.name, 'hdri': {_py(p)}, 'strength': {float(strength)}}}
"""
    return _ok(_run_bpy(code))


# --------------------------------------------------------------------------- animation

@mcp.tool()
def set_frame_range(start: int = 1, end: int = 250, fps: int = 24, current: int = None) -> str:
    """Set scene frame range and fps."""
    cur = f"s.frame_set(int({int(current)}))" if current is not None else ""
    code = f"""
import bpy
s = bpy.context.scene
s.frame_start = int({int(start)})
s.frame_end = int({int(end)})
s.render.fps = int({int(fps)})
{cur}
_result = {{'frame_start': s.frame_start, 'frame_end': s.frame_end, 'fps': s.render.fps, 'current': s.frame_current}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def insert_keyframe(object_name: str, frame: int, location: list = None,
                    rotation: list = None, scale: list = None) -> str:
    """Insert keyframes for the given channels of an object at a frame.
    rotation in DEGREES. Omitted channels are left untouched."""
    import math
    lines = [f"o = bpy.data.objects.get({_py(object_name)})",
             f"if o is None: raise ValueError('object not found: {object_name}')",
             f"bpy.context.scene.frame_set(int({int(frame)}))"]
    if location is not None:
        lines.append(f"o.location = {_py([float(v) for v in location])}")
        lines.append(f"o.keyframe_insert(data_path='location', frame={int(frame)})")
    if rotation is not None:
        lines.append(f"o.rotation_euler = {_py([math.radians(float(v)) for v in rotation])}")
        lines.append(f"o.keyframe_insert(data_path='rotation_euler', frame={int(frame)})")
    if scale is not None:
        lines.append(f"o.scale = {_py([float(v) for v in scale])}")
        lines.append(f"o.keyframe_insert(data_path='scale', frame={int(frame)})")
    lines.append("_result = {'object': o.name, 'frame': bpy.context.scene.frame_current}")
    return _ok(_run_bpy("import bpy\n" + "\n".join(lines)))


@mcp.tool()
def get_animation_info() -> str:
    """List animated objects and their F-curves (paths + keyframe counts)."""
    code = """
import bpy
out = []
for o in bpy.data.objects:
    if o.animation_data and o.animation_data.action:
        curves = []
        for fc in o.animation_data.action.fcurves:
            curves.append({'data_path': fc.data_path, 'array_index': fc.array_index,
                           'keyframe_count': len(fc.keyframe_points)})
        out.append({'object': o.name, 'action': o.animation_data.action.name, 'fcurves': curves})
_result = {'animated_objects': out, 'frame_start': bpy.context.scene.frame_start,
           'frame_end': bpy.context.scene.frame_end, 'fps': bpy.context.scene.render.fps}
"""
    return _ok(_run_bpy(code))


# --------------------------------------------------------------------------- render

@mcp.tool()
def set_render_settings(engine: str = "CYCLES", resolution_x: int = 640, resolution_y: int = 480,
                        samples: int = 32, fps: int = 24, frame_start: int = None,
                        frame_end: int = None, file_format: str = "PNG",
                        film_transparent: bool = False) -> str:
    """Configure the render. engine: CYCLES (CPU, works headless), BLENDER_WORKBENCH
    or BLENDER_EEVEE_NEXT (needs GPU, may fail headless). file_format: PNG, JPEG, EXR, TIFF."""
    eng = engine.upper()
    if eng not in ("CYCLES", "BLENDER_WORKBENCH", "BLENDER_EEVEE_NEXT"):
        raise ValueError("engine must be CYCLES, BLENDER_WORKBENCH or BLENDER_EEVEE_NEXT")
    fmt = file_format.upper()
    if fmt not in ("PNG", "JPEG", "EXR", "TIFF", "BMP"):
        raise ValueError("file_format must be PNG, JPEG, EXR, TIFF or BMP")
    code = f"""
import bpy
s = bpy.context.scene
s.render.engine = {_py(eng)}
s.render.resolution_x = int({int(resolution_x)})
s.render.resolution_y = int({int(resolution_y)})
s.render.resolution_percentage = 100
s.render.fps = int({int(fps)})
s.render.image_settings.file_format = {_py(fmt)}
s.render.film_transparent = {bool(film_transparent)}
if {_py(frame_start)} is not None: s.frame_start = int({_py(frame_start)})
if {_py(frame_end)} is not None: s.frame_end = int({_py(frame_end)})
try:
    s.cycles.samples = int({int(samples)})
    s.cycles.use_denoising = False
except Exception as e:
    print('cycles samples not applied:', e)
_result = {{'engine': s.render.engine, 'resolution': [s.render.resolution_x, s.render.resolution_y],
            'samples': getattr(getattr(s, 'cycles', None), 'samples', None), 'format': s.render.image_settings.file_format}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def render_still(name: str = "render", project: str = "", samples: int = None,
                 resolution_x: int = None, resolution_y: int = None, timeout_seconds: int = 900) -> str:
    """Render the current camera to /data/renders/<name>_<timestamp>.png (or under
    /data/projects/<project>/renders/ if project is given). Returns the file path."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{name}_{ts}.png"
    if project:
        outdir = _safe_path(os.path.join("projects", project, "renders"))
    else:
        outdir = os.path.join(DATA_DIR, "renders")
    os.makedirs(outdir, exist_ok=True)
    outpath = os.path.join(outdir, fname)
    overrides = ""
    if samples is not None:
        overrides += f"\ntry:\n    s.cycles.samples = int({int(samples)})\nexcept Exception: pass"
    if resolution_x:
        overrides += f"\ns.render.resolution_x = int({int(resolution_x)})"
    if resolution_y:
        overrides += f"\ns.render.resolution_y = int({int(resolution_y)})"
    code = f"""
import bpy, os
s = bpy.context.scene
{overrides}
s.render.filepath = {_py(outpath)}
s.render.image_settings.file_format = 'PNG'
if s.camera is None:
    raise ValueError('no active camera in the scene --- add one with add_camera()')
bpy.ops.render.render(write_still=True)
size = os.path.getsize({_py(outpath)}) if os.path.exists({_py(outpath)}) else 0
_result = {{'render': {_py(outpath)}, 'bytes': size}}
"""
    return _ok(_run_bpy(code, timeout=float(timeout_seconds)))


@mcp.tool()
def render_animation(name: str = "anim", project: str = "", timeout_seconds: int = 1800) -> str:
    """Render the current frame range as a PNG sequence into
    /data/renders/<name>_<timestamp>/ (or the project folder)."""
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    if project:
        outdir = _safe_path(os.path.join("projects", project, "renders", f"{name}_{ts}"))
    else:
        outdir = os.path.join(DATA_DIR, "renders", f"{name}_{ts}")
    os.makedirs(outdir, exist_ok=True)
    code = f"""
import bpy, os
s = bpy.context.scene
if s.camera is None:
    raise ValueError('no active camera in the scene')
s.render.filepath = {_py(outdir + '/frame_')}
s.render.image_settings.file_format = 'PNG'
bpy.ops.render.render(animation=True, write_still=True)
count = len([f for f in os.listdir({_py(outdir)}) if f.endswith('.png')])
_result = {{'directory': {_py(outdir)}, 'frames_written': count}}
"""
    return _ok(_run_bpy(code, timeout=float(timeout_seconds)))


@mcp.tool()
def get_render_image(path: str):
    """Return a rendered image (PNG/JPEG) from under /data so the client can view it."""
    p = _safe_path(path, must_exist=True)
    if _Image is None:
        return _ok({"path": p, "note": "image content not supported by this mcp build; open the path on the server"})
    return _Image(path=p)


# --------------------------------------------------------------------------- import / export

@mcp.tool()
def import_model(path: str, new_name: str = "") -> str:
    """Import a model file under /data (.glb, .gltf, .fbx, .obj, .stl)."""
    p = _safe_path(path, must_exist=True)
    ext = os.path.splitext(p)[1].lower()
    if ext in (".glb", ".gltf"):
        op = f"bpy.ops.import_scene.gltf(filepath={_py(p)})"
    elif ext == ".fbx":
        op = f"bpy.ops.import_scene.fbx(filepath={_py(p)})"
    elif ext == ".obj":
        op = f"try:\n    bpy.ops.wm.obj_import(filepath={_py(p)})\nexcept Exception:\n    bpy.ops.import_scene.obj(filepath={_py(p)})"
    elif ext == ".stl":
        op = f"bpy.ops.wm.stl_import(filepath={_py(p)})"
    else:
        raise ValueError("unsupported format. Use .glb/.gltf/.fbx/.obj/.stl")
    rename_code = f"if new_objs:\n    new_objs[0].name = {_py(new_name)}" if new_name else ""
    code = f"""
import bpy
before = set(bpy.data.objects)
{op}
new_objs = [o for o in bpy.data.objects if o not in before]
{rename_code}
_result = {{'imported': [o.name for o in new_objs], 'count': len(new_objs)}}
"""
    return _ok(_run_bpy(code))


@mcp.tool()
def export_scene(export_format: str, name: str = "export", project: str = "") -> str:
    """Export the scene under /data. export_format: GLB, FBX or OBJ."""
    fmt = export_format.upper()
    ext = {"GLB": ".glb", "GLTF": ".glb", "FBX": ".fbx", "OBJ": ".obj"}.get(fmt)
    if ext is None:
        raise ValueError("export_format must be GLB, FBX or OBJ")
    if project:
        outdir = _safe_path(os.path.join("projects", project, "exports"))
    else:
        outdir = os.path.join(DATA_DIR, "exports")
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    outpath = os.path.join(outdir, f"{name}_{ts}{ext}")
    if fmt in ("GLB", "GLTF"):
        op = f"bpy.ops.export_scene.gltf(filepath={_py(outpath)}, export_format='GLB')"
    elif fmt == "FBX":
        op = f"bpy.ops.export_scene.fbx(filepath={_py(outpath)})"
    else:
        op = f"try:\n    bpy.ops.wm.obj_export(filepath={_py(outpath)})\nexcept Exception:\n    bpy.ops.export_scene.obj(filepath={_py(outpath)})"
    code = f"""
import bpy, os
{op}
_result = {{'export': {_py(outpath)}, 'bytes': os.path.getsize({_py(outpath)}) if os.path.exists({_py(outpath)}) else 0}}
"""
    return _ok(_run_bpy(code, timeout=600))


# --------------------------------------------------------------------------- files & logs

@mcp.tool()
def list_files(subdir: str = "", max_depth: int = 3) -> str:
    """List files under /data (optionally a subdir like 'projects' or 'renders'),
    with relative path, size and mtime."""
    base = _safe_path(subdir) if subdir else DATA_DIR
    out = []
    root_len = len(os.path.realpath(DATA_DIR)) + 1
    for dirpath, dirs, files in os.walk(base):
        depth = os.path.relpath(dirpath, base).count(os.sep) + 1 if os.path.relpath(dirpath, base) != "." else 0
        if depth > max_depth:
            dirs[:] = []
            continue
        for f in files:
            full = os.path.join(dirpath, f)
            st = os.stat(full)
            out.append({"path": os.path.realpath(full)[root_len:] if full.startswith(DATA_DIR) else full,
                        "bytes": st.st_size,
                        "modified": datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")})
        if len(out) > 500:
            break
    return _ok(out)


@mcp.tool()
def get_logs(log: str = "both", lines: int = 100) -> str:
    """Tail the Blender and/or MCP logs ('blender', 'mcp' or 'both')."""
    targets = {"blender": ["blender.log"], "mcp": ["mcp.log"],
               "both": ["blender.log", "mcp.log"]}.get(log.lower(), ["blender.log", "mcp.log"])
    out = {}
    for t in targets:
        p = os.path.join(DATA_DIR, "logs", t)
        if os.path.exists(p):
            with open(p, "r", errors="replace") as f:
                out[t] = f.readlines()[-lines:]
        else:
            out[t] = []
    return _ok(out)


@mcp.tool()
def disk_usage() -> str:
    """Disk usage/free space of the /data volume."""
    usage = shutil.disk_usage(DATA_DIR)
    counts = {d: sum(len(files) for _, _, files in os.walk(os.path.join(DATA_DIR, d))) for d in SUBDIRS}
    return _ok({"total_gb": round(usage.total / 2**30, 2), "used_gb": round(usage.used / 2**30, 2),
                "free_gb": round(usage.free / 2**30, 2), "file_counts": counts})


# --------------------------------------------------------------------------- escape hatch

@mcp.tool()
def execute_blender_code(code: str, timeout_seconds: int = 300) -> str:
    """Run arbitrary Python INSIDE the Blender process with full bpy access.
    Assign to a variable named `_result` to return structured data (print() output
    is captured too). Use for anything the structured tools don't cover."""
    resp = _bridge_call({"id": os.urandom(8).hex(), "type": "exec", "params": {"code": code}},
                        timeout=float(timeout_seconds))
    if resp.get("status") != "ok":
        raise RuntimeError(resp.get("message", "Blender error"))
    return _ok({"result": resp.get("result"), "stdout": resp.get("stdout"), "stderr": resp.get("stderr")})


# --------------------------------------------------------------------------- ASGI wrapper + auth

class BearerAuth:
    """Pure-ASGI middleware: /health open, everything else needs Bearer token
    (only when BLENDER_MCP_TOKEN is set)."""

    def __init__(self, app, token):
        self.app = app
        self.token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        if path == "/health" or not self.token:
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        auth = headers.get(b"authorization", b"").decode("latin-1")
        if auth == f"Bearer {self.token}":
            await self.app(scope, receive, send)
            return
        body = b'{"error":"unauthorized","hint":"send Authorization: Bearer <BLENDER_MCP_TOKEN>"}'
        await send({"type": "http.response.start", "status": 401,
                    "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
        await send({"type": "http.response.body", "body": body})


class HealthAndMCP:
    """Route /health without auth; everything else goes to the MCP Starlette app."""

    def __init__(self, mcp_app):
        self.mcp_app = mcp_app

    def _bridge_state(self):
        """Cheap TCP probe of the Blender bridge (no Blender call)."""
        try:
            with socket.create_connection((BRIDGE_HOST, BRIDGE_PORT), 2):
                return "up"
        except OSError:
            return "down"

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path") == "/health":
            bridge = self._bridge_state()
            body = json.dumps({"status": "ok" if bridge == "up" else "degraded",
                               "service": "blender-mcp",
                               "blender_bridge": bridge,
                               "token_configured": bool(TOKEN)}).encode()
            await send({"type": "http.response.start", "status": 200,
                        "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]})
            await send({"type": "http.response.body", "body": body})
            return
        await self.mcp_app(scope, receive, send)


if __name__ == "__main__":
    import uvicorn

    inner = mcp.streamable_http_app()
    app = BearerAuth(HealthAndMCP(inner), TOKEN)
    if not TOKEN:
        print("[mcp] WARNING: BLENDER_MCP_TOKEN is not set --- server is UNAUTHENTICATED", flush=True)
    print(f"[mcp] Blender MCP server on 0.0.0.0:{PORT} (path /mcp)", flush=True)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="info")
