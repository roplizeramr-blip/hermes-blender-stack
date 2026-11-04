---
name: blender-procedural-modeling
description: Use when building geometry procedurally in Blender headless — arrays, mirrors, repeated patterns, parametric objects via Python (bpy) executed through the blender MCP.
---

# Procedural Modeling (headless)

Build complex geometry from small parametric building blocks using `mcp_blender_execute_blender_code`.

## Pattern

1. Design the parametric recipe (profile curve, count, spacing, rotation).
2. Run one code block that: resets nothing (work on the current scene), loops over the parameter space, uses `bpy.ops.mesh.primitive_*` or bmesh/mathutils.
3. Assign `_result` to a dict with created object names.
4. Verify with `mcp_blender_get_scene_info` or `mcp_blender_get_object_info`.

## Example — row of arches

```python
import bpy, math
created = []
for i in range(6):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(i*2.2, 0, 1.0))
    o = bpy.context.active_object
    o.name = f"arch_{i}"
    o.scale = (1.0, 0.4, 2.0)
    created.append(o.name)
_result = {"created": created}
```

## Useful building blocks

- Modifiers for repetition: ARRAY (`count`, `relative_offset_displace`), MIRROR (`use_axis`), BEVEL (`width`, `segments`), SUBSURF (`levels`). Call `mcp_blender_add_modifier`.
- `mcp_blender_duplicate_object` for copies, then `set_transform`.
- Collections per assembly: `mcp_blender_create_collection` + `move_to_collection`.
- Mathutils: `from mathutils import Vector, Matrix` for placements.

## Pitfalls

- bpy operators need a context; in background mode `bpy.ops.object.*` works for primitives/modifiers but not for UI-dependent operators (e.g. bevel in edit mode) — prefer modifier-based or mesh-data approaches.
- Keep scripts idempotent: delete/rebuild by name prefix, don't accumulate duplicates.
- Large loops (thousands of objects) are slow; prefer modifiers or linked duplicates.
- Always end with `_result = {...}` (JSON-serializable) — non-serializable values become repr strings.

## العربية (Arabic)

- **اسم المهارة:** النمذجة الإجرائية — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "ابني جبل بت Modifierノイズ مع Displace texture."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `add_modifier -> execute_blender_code (Noise/Voronoi texture nodes) -> set_transform -> get_scene_info` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
