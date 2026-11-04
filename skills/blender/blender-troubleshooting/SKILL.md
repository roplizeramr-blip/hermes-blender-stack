---
name: blender-troubleshooting
description: Use when something fails in the blender MCP — connection errors, bridge/Blender crashes, black renders, missing tools, wrong paths, MCP reconnects, and log inspection.
---

# Troubleshooting (blender MCP)

## Fast triage order

1. `mcp_blender_health` — is the bridge alive? Returns Blender version + disk free.
2. `mcp_blender_get_logs log lines` — `blender` (bridge/Blender stdout), `mcp` (server), or `both`.
3. `mcp_blender_get_scene_info` — is the scene/session healthy?
4. Your last tool call's error message (Blender tracebacks come back verbatim).

## Common failures & fixes

| Symptom | Cause | Fix |
|---|---|---|
| `mcp` unreachable / 401 | wrong/missing Bearer token | Check MCP config header (`Authorization: Bearer <BLENDER_MCP_TOKEN>`); /health endpoint is open for probes. |
| Bridge connection refused | Blender process died or still starting | Wait 10–20s after (re)deploy; check `get_logs blender`; check `/data/logs/blender.log`. |
| `no active camera` on render | scene has no camera | `add_camera` first, or look at get_scene_info. |
| Black render | no world light / no lights | `set_world` or add POINT/SUN; see blender-lighting. |
| EEVEE errors | no GPU headless | `set_render_settings engine=CYCLES`. |
| Timeout on render | too many samples/px | Lower samples/resolution; raise timeout_seconds. |
| `path must be under /data` | absolute host path used | Use /data-relative paths only. |
| Objects vanish after operations | scene reset (`reset_scene`, `new_project`, `open_blend`) | Rebuild or re-open; save often. |
| Tool returns repr instead of JSON | value not JSON-serializable | Restructure `_result` into dict/list/str/num. |

## Persistence notes

- `/data` is the only persistent filesystem (projects, renders, logs, backups, blender install itself + python venv — installed on first boot).
- Container restarts re-run `start.sh`: cached Blender/venv are reused; logs go to /data/logs/.
- The Blender bridge child process is not supervised inside the container — if it dies, MCP calls fail with connection refused. Redeploy the app (or ask the operator to restart it) to clear the state.

## Deep diagnostics

- `mcp_blender_execute_blender_code code` with e.g. `bpy.app.version`, `bpy.context.scene.name`, `bpy.data.objects.keys()`.
- `mcp_blender_disk_usage` if writes start failing (disk full).
- After fixes, re-run `health` and one real tool (`get_scene_info`) before claiming success.

## العربية (Arabic)

- **اسم المهارة:** استكشاف الأخطاء وإصلاحها — استخدم هذه المهارة تلقائيًا عندما يكتب المستخدم طلبه بالعربية.
- **مثال طلب بالعربية:** "الصورة سودا والرندر بياخد وقت طويل، ساعدني."
- **قاعدة اللغة:** أسماء الأدوات تُستدعى بالإنجليزية دائمًا (`mcp_blender_*`)، لكن اشرح النتيجة للمستخدم **بالعربية** (أو bilanguage: عربي + English عند الحاجة).
- **التسلسل العملي للمثال:** `health -> get_logs -> get_scene_info -> disk_usage -> set_render_settings -> render_still` — نفّذه خطوة بخطوة، وتحقق بعد كل مرحلة بـ `mcp_blender_get_scene_info` أو `mcp_blender_get_object_info`.
- **قبل أي أمر على الملفات:** تأكد أن المسار تحت `/data` (`projects/`, `renders/`, `assets/`, `exports/`, `backups/`) وأن المشروع محفوظ بـ `mcp_blender_save_scene`.
