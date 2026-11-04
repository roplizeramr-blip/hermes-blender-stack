---
name: blender-materials
description: Use when creating or editing materials and textures in Blender headless — Principled BSDF, metallic/roughness/IOR, transmission, emission, assigning materials, listing materials.
---

# Materials & Texturing (headless)

## Core tools

- `mcp_blender_create_material name color metallic roughness ior transmission emission_color emission_strength assign_to`
  - `color`: `"#RRGGBB"` or `[r,g,b,a]` (0-1 floats).
  - `metallic` / `roughness` / `transmission`: 0-1 floats.
  - `ior`: 1.45 default (1.0 air, 1.33 water, 1.5 glass).
  - `emission_color` + `emission_strength` for glow (screens, lamps, neon).
- `mcp_blender_assign_material object_name material` — append existing material to an object.
- `mcp_blender_list_materials` — dump all materials with BSDF values.

## Recipes

- Gold: color="#D4AF37", metallic=1.0, roughness=0.15.
- Brushed steel: color="#C0C0C0", metallic=1.0, roughness=0.35.
- Matte rubber: color="#1a1a1a", metallic=0.0, roughness=0.9.
- Clear glass: color="#ffffff", metallic=0.0, roughness=0.05, transmission=1.0, ior=1.5.
- Emission panel: emission_color="#ffffff", emission_strength=5.

## Notes

- Materials are created with nodes; BSDF input names in Blender 4.5: `Base Color`, `Metallic`, `Roughness`, `IOR`, `Transmission Weight`, `Emission Color`, `Emission Strength`.
- If a color string fails, pass `[r,g,b,a]` floats instead of hex.
- Procedural textures: use `mcp_blender_execute_blender_code` to add Noise/Voronoi/Wave/Gradient texture nodes and link into Principled inputs; set `_result = {'ok': True}` at the end.
- Images stored under /data/textures can be loaded via `bpy.data.images.load()` inside code, or use `mcp_blender_world_hdri` for environment maps.

## العربية (Arabic)

- **اسم المهارة:** الخامات والنسيج — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "خلي الكروت دهبي معدني والكرة زجاج شفاف."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `create_material -> assign_material -> list_materials` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
