---
name: blender-lighting
description: Use when lighting a scene in Blender headless — POINT/SUN/SPOT/AREA lights, world background/HDRI, energy values, and light placement for good renders.
---

# Lighting (headless)

## Core tools

- `mcp_blender_add_light light_type name location rotation energy color`
  - `light_type`: POINT, SUN, SPOT, AREA.
  - `energy`: Watts for POINT/SPOT/AREA (typical interior point light 200–1500); SUN is irradiance (1–5 typical).
  - `rotation` in DEGREES (matters for SUN direction, SPOT and AREA orientation).
- `mcp_blender_set_world color strength` — flat world background; acts as ambient fill in Cycles. strength 0.2–2.0 typical.
- `mcp_blender_world_hdri image_path strength` — use an .hdr/.exr under /data as environment (image_path must be under /data).

## Recipes

- Three-point lighting:
  1. Key: AREA light at (4, -4, 5), rotation aimed at subject (or use SPOT with look rotation), energy 800, color "#fff4e6".
  2. Fill: AREA at (-5, -3, 3), energy 300, color "#e6f0ff".
  3. Rim: SPOT or POINT behind subject at (0, 5, 4), energy 500.
- Outdoor: add_light(light_type="SUN", energy=3.0, rotation=[45, -30, 0]) + set_world(color="#87ceeb", strength=0.6) or world_hdri.
- Studio softbox: large AREA (location above, energy 1200) + world strength 0.3.

## Verification

- After lighting, call `mcp_blender_get_scene_info` to list lights, then render a test frame (`mcp_blender_render_still`) and inspect with `mcp_blender_get_render_image path`.
- If the scene is pitch black: no world set, no lights, or camera looking at dark side. Fix by raising `set_world` strength or adding a POINT near the subject.
- Cycles uses physically-based falloff for point lights (inverse square) — small rooms need high energies.

## العربية (Arabic)

- **اسم المهارة:** الإضاءة — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "أضف إضاءة ثلاثية النقاط وحسّن الإضاءة مع خلفية رمادية."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `add_light -> set_world -> get_scene_info -> render_still (للتحقق)` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
