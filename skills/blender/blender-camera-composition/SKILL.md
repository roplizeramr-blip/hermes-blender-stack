---
name: blender-camera-composition
description: Use when adding cameras or composing shots in Blender headless — placement, look_at aiming, lens length (mm), framing, active camera selection, rule of thirds.
---

# Camera & Composition (headless)

## Core tools

- `mcp_blender_add_camera name location look_at rotation lens`
  - `look_at=[x,y,z]`: aim the camera at a target point (recommended).
  - `rotation` in DEGREES as alternative.
  - `lens`: mm; 18–24 wide, 35 normal-ish, 50 standard, 85 portrait, 135+ tele.
- `mcp_blender_set_active_camera name`
- `mcp_blender_get_scene_info` — lists cameras and active_camera.

## Recipes

- Product shot: add_camera(location=[4, -6, 3], look_at=[0,0,1], lens=50).
- Architectural wide: location=[-6, -8, 4], look_at=[0,0,2], lens=24.
- Portrait/detail: lens=85, closer location.
- Hero angle: slightly below subject, lens=35, look_at at 40% height of subject.

## Framing guidance

- Subject centered vs thirds: offset camera target by ±10–15% for dynamic composition.
- Keep horizon level: avoid roll (rotation around view axis) — only X/Z matter for `look_at`.
- Fill roughly 60–75% of frame height for hero subjects.
- Check `resolution_x/y` in render settings; vertical compositions need portrait resolution via set_render_settings.

## Verification loop

1. Add camera → 2. `mcp_blender_set_render_settings resolution_x=640 resolution_y=360` → 3. `mcp_blender_render_still` → 4. `mcp_blender_get_render_image <path>` to view the frame → 5. Adjust location/lens/look_at → repeat.

## العربية (Arabic)

- **اسم المهارة:** الكاميرا والتكوين — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "حط الكاميرا面对 الكروت وزوّل عليها."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `add_camera(look_at) -> set_active_camera -> get_scene_info` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
