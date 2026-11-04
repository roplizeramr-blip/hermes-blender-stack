---
name: blender-asset-management
description: Use when managing Blender projects, files and assets — project folders, saving .blend with auto-backup, listing files, workspace disk usage, importing/exporting models, keeping versions without overwriting work.
---

# Asset & Project Management

## Layout on disk (/data volume)

```
/data/projects/<project>/        # .blend files per project (+ optional renders/exports/)
/data/renders/                   # standalone render outputs
/data/assets/                    # downloaded/imported source assets
/data/textures/                  # textures, HDRIs
/data/exports/                   # .glb/.fbx/.obj exports
/data/logs/                      # blender.log, mcp.log
/data/backups/                   # automatic backups made by save_scene/backup_project
```

## Core tools

- `mcp_blender_new_project name` — folder + empty scene + initial .blend.
- `mcp_blender_list_projects` — all projects with blend files + sizes.
- `mcp_blender_save_scene project name` — overwrite-protected save (old file copied to /data/backups with timestamp).
- `mcp_blender_open_blend path` (under /data), `mcp_blender_backup_project project`.
- `mcp_blender_list_files subdir max_depth` — paths, sizes, mtimes.
- `mcp_blender_disk_usage` — free space + per-folder file counts.
- `mcp_blender_import_model path new_name` (.glb/.gltf/.fbx/.obj/.stl, under /data).
- `mcp_blender_export_scene export_format name project` (GLB/FBX/OBJ).
- `mcp_blender_reset_scene` — empty factory scene (files untouched).

## Rules

- Never edit files outside /data — it is the only persistent location.
- Before any risky change, `save_scene` (auto-backup) or `backup_project`.
- Versioning: new `name` per iteration (shot_v001.blend); `save_scene` never destroys previous versions.
- Exports go to exports/ (or project/exports for GLB delivery); renders to renders/.
- Report exact absolute paths back to the user so files can be retrieved; also summarize `list_files` when asked "where is it".

## العربية (Arabic)

- **اسم المهارة:** إدارة الأصول — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "احفظ المشروع واعمل backup واستورد ملف OBJ."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `save_scene -> backup_project -> import_model -> export_scene -> list_files` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
