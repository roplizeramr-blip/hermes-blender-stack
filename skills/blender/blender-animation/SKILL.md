---
name: blender-animation
description: Use when animating objects in Blender headless — frame ranges, keyframes for location/rotation/scale, fps, listing animation curves, rendering frame sequences.
---

# Animation (headless)

## Core tools

- `mcp_blender_set_frame_range start end fps current` — e.g. 1..250 @ 24fps.
- `mcp_blender_insert_keyframe object_name frame location rotation scale` — DEGREES for rotation; only provided channels get keyed.
- `mcp_blender_get_animation_info` — animated objects + F-curves (paths, keyframe counts).
- `mcp_blender_render_animation name project timeout_seconds` — renders frame range as PNG sequence into /data/renders/<name>_<ts>/.

## Workflow

1. `set_frame_range(start=1, end=96, fps=24)`.
2. Frame 1: position object, `insert_keyframe(frame=1, location=[...], rotation=[...])`; frame 48/96: new transforms, key again.
3. `get_animation_info` to confirm curves.
4. `render_still` at a mid frame to sanity-check, then `render_animation` for the full sequence.

## Tips

- Insert at least two keys per animated property.
- For loops use `repeat` via execute_blender_code (linear interpolation is default for object transforms).
- Rendering long ranges is slow on CPU Cycles — render a few test stills before full sequence; lower samples via `set_render_settings samples=16`.
- `render_animation` blocks; pass `timeout_seconds` generously (default 1800).
- Save often: `mcp_blender_save_scene project name` (auto-backup in /data/backups).

## العربية (Arabic)

- **اسم المهارة:** التحريك (Animation) — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "حرّك الكرة لفوق على طول 24 فريم."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `set_frame_range -> insert_keyframe -> get_animation_info -> render_animation` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
