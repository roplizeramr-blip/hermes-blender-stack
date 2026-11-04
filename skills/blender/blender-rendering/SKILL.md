---
name: blender-rendering
description: Use when configuring and running renders in Blender headless — Cycles setup, resolution, samples, output paths, PNG/EXR, render time management, viewing the result.
---

# Rendering (headless)

## Core tools

- `mcp_blender_set_render_settings engine resolution_x resolution_y samples fps frame_start frame_end file_format film_transparent`
  - engine: `CYCLES` (works headless on CPU — default), `BLENDER_WORKBENCH`, `BLENDER_EEVEE_NEXT` (usually fails headless, GPU needed).
  - file_format: PNG (default), JPEG, EXR, TIFF, BMP.
- `mcp_blender_render_still name project samples resolution_x resolution_y timeout_seconds`
  - Writes /data/renders/<name>_<timestamp>.png (or under a project) and returns the path + bytes.
- `mcp_blender_render_animation` — frame sequence into a folder.
- `mcp_blender_get_render_image path` — returns the image so you can see it.

## Realistic budget (free tier, 1–2 shared vCPU)

- Preview: 320×180, 8–16 samples — seconds per frame.
- Working: 640×360, 32 samples — tens of seconds.
- Final still: 1280×720, 64–128 samples — minutes; only when scene is final.
- Denoising is OFF (speed); reduce noise by lighting better rather than more samples.

## Workflow

1. Confirm camera exists (`get_scene_info`).
2. `set_render_settings(engine="CYCLES", resolution_x=640, resolution_y=360, samples=32)`.
3. `render_still(name="shot01")`.
4. `get_render_image(path=<returned path>)` and inspect.
5. Fix lighting/materials, re-render.
6. Save the blend (`save_scene`) so the render is reproducible.

## Failure modes

- "no active camera" → `add_camera` first.
- Black image → see blender-lighting (world + key light).
- Timeout → lower resolution/samples; raise `timeout_seconds`.
- Engine error (EEVEE headless) → switch to CYCLES.

## العربية (Arabic)

- **اسم المهارة:** العرض والتصيير — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "اعمل رندر للصورة بأبعاد 640x360 مع 32 samples."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `set_render_settings -> render_still -> get_render_image -> save_scene` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
