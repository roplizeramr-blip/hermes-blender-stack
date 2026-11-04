---
name: blender-scene-design
description: Use when designing or reviewing a full 3D scene — layout planning, scale/proportions, cameras and composition, light design, materials, performance, and pre-render checks in Blender headless.
---

# Scene Design (headless)

## Checklist-driven workflow

1. **Brief**: subject, mood, final framing, output (still/sequence).
2. **Blockout**: primitives for every major mass (`create_primitive`), correct real-world scale (meters). Organize into collections (`create_collection`, `move_to_collection`).
3. **Materials**: one material per surface family (`create_material`); verify with `list_materials`.
4. **Lighting**: key/fill/rim (`add_light`) + world ambient (`set_world` or `world_hdri`). See the blender-lighting skill.
5. **Camera**: one primary camera (`add_camera`), verify framing with `render_still` + `get_render_image`. See the blender-camera-composition skill.
6. **Polish**: smooth shading (`set_shade_smooth`), bevels/modifiers for edge highlights (`add_modifier`), background elements for depth.
7. **Pre-render audit**:
   - `get_scene_info` — object count sane, camera set, lights ≥ 2, materials assigned.
   - No object at origin unintentionally (scale 0 or NaN transforms).
   - Frame range/fps if animated.
8. **Save**: `save_scene` before any render that matters; `new_project` for multi-scene work.

## Composition rules of thumb

- One clear hero object; supporting elements arc toward it (leading lines).
- Vary silhouette sizes (large/medium/small).
- Keep 20–30% negative space.
- Match light temperature to mood (warm interior / cool exterior).

## Performance

- Prefer modifiers over dense hand-placed geometry.
- Headless Cycles: keep samples ≤ 64 for previews; final still 128–256 if time permits.
- EEVEE headless will typically fail (no GPU context) — use Cycles or Workbench.

## العربية (Arabic)

- **اسم المهارة:** تصميم المشهد — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "صمم مشهد استوديو بسيط فيه أرضية ومجسمات موزّعة."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `new_project -> create_collection -> create_primitive -> move_to_collection -> save_scene` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
