---
name: blender-3d-modeling
description: Use when modeling 3D objects in Blender headless via the blender MCP — primitives, transforms, modifiers, collections, and scene information.
---

# Blender 3D Modeling (headless)

You control a headless Blender 4.5 LTS through the `blender` MCP server. Tools are registered as `mcp_blender_<tool>`.

## Core tools

- `mcp_blender_health` — liveness + Blender version + disk space.
- `mcp_blender_get_scene_info` — objects, collections, materials, cameras, lights, frame range, engine.
- `mcp_blender_get_object_info name` — one object's transform, modifiers, materials, mesh stats.
- `mcp_blender_create_primitive primitive_type name size location rotation scale collection` — CUBE, UV_SPHERE, ICO_SPHERE, CYLINDER, CONE, PLANE, TORUS, MONKEY. `rotation` is in DEGREES.
- `mcp_blender_set_transform object_name location rotation scale` — absolute transforms.
- `mcp_blender_duplicate_object name new_name`, `mcp_blender_delete_object name`
- `mcp_blender_create_collection name`, `mcp_blender_list_collections`, `mcp_blender_move_to_collection`
- `mcp_blender_add_modifier object_name modifier_type settings` — SUBSURF, BEVEL, MIRROR, ARRAY, SOLIDIFY, DECIMATE, WIREFRAME. Example settings: `{"levels": 2}` (SUBSURF), `{"width": 0.1}` (BEVEL), `{"count": 3, "relative_offset_displace": [2,0,0]}` (ARRAY).
- `mcp_blender_set_shade_smooth object_name smooth true`

## Workflow

1. `get_scene_info` first to see what exists.
2. Create primitives, then apply transforms/modifiers.
3. Verify with `get_scene_info` / `get_object_info`.

## Rules

- Rotations are DEGREES, not radians.
- All file paths must live under `/data` (projects, renders, assets, exports, backups).
- For anything the structured tools can't express, use `mcp_blender_execute_blender_code code` — assign to a variable named `_result` to return data.
- Save with `mcp_blender_save_scene` — it auto-backs up overwritten files to /data/backups.

## العربية (Arabic)

- **اسم المهارة:** النمذجة ثلاثية الأبعاد — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "صمم مكعب ومكعبة على أرضية، وحطهم في مجموعة تسمى Demo."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `get_scene_info -> create_primitive(CUBE / UV_SPHERE / PLANE) -> set_transform -> move_to_collection -> get_scene_info` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
