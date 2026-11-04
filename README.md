# Hermes × Blender Stack

Two Docker applications that work as one AI system:

| App | Image | Port | Purpose |
|---|---|---|---|
| **Hermes AI Agent** | `ghcr.io/roplizeramr-blip/hermes-blender-stack-hermes:latest` | 9119 | The brain: chat WebUI (Arabic/English), MCP client, skills engine, sessions, cron, file browser |
| **Blender MCP Server** | `ghcr.io/roplizeramr-blip/hermes-blender-stack-blender-mcp:latest` | 8080 | Headless Blender 4.5.15 LTS + MCP server (39 tools) + nginx front |

```
browser ──HTTPS──► Hermes WebUI :9119 ──MCP(streamable HTTP + Bearer)──► Blender MCP :8080
                       │                                                        │
                       │ skills/ (10 SKILL.md)                                │ Blender bridge
                       ▼                                                        │ (127.0.0.1:9876)
                  LLM provider (API key)                                  headless Blender
```

## Repository layout

```
blender-mcp/                 # Blender MCP server app
  Dockerfile                 # debian:bookworm-slim + Blender 4.5.15 LTS baked in
  entrypoint.sh              # supervises Blender + MCP server + nginx
  mcp_server.py              # FastMCP server, 39 tools, bearer auth
  blender_bridge.py          # socket bridge into the Blender process
  nginx.conf                 # public :8080 → uvicorn :8000 → bridge :9876
  index.html                 # status landing page
hermes/                      # Hermes Agent app
  Dockerfile                 # FROM nousresearch/hermes-agent:latest
  cont-init.d/20-hermes-blender   # boot hook: seeds skills, registers the MCP server
  scripts/configure_blender.py    # merges mcp_servers.blender + model config
skills/blender/              # 10 agentskills.io Blender skills (bilingual)
.github/workflows/build.yml  # builds + pushes both images to GHCR
docs/DEPLOYMENT.md           # exact deploy procedure for CranL
```

## The 10 Blender skills

Every one of them maps to real tools of the MCP server (39 tools, full coverage):

| Skill | Covers |
|---|---|
| `blender-3d-modeling` | primitives, transforms, modifiers, collections |
| `blender-procedural-modeling` | procedural textures, displacement, geometry nodes |
| `blender-materials` | Principled BSDF, metallic/roughness/glass/emission |
| `blender-lighting` | area/sun/point lights, world, HDRI |
| `blender-camera-composition` | camera placement, look-at, active camera |
| `blender-animation` | keyframes, frame range, animation render |
| `blender-scene-design` | project layout, collections, naming |
| `blender-rendering` | Cycles/Workbench, resolution, samples, PNG/EXR |
| `blender-asset-management` | save/backup/import/export, file inventory |
| `blender-troubleshooting` | health, logs, disk usage, recovery recipes |

Every skill also carries an **Arabic** section: tool calls stay in English
(`mcp_blender_*`), the answer is written back in Arabic.

## Build

```bash
# Both images are built by GitHub Actions on every push to main
gh workflow run build-images
```

## Deploy on CranL

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full procedure
(`create_docker_app` with the GHCR images, volumes, env vars and the
Hermes ⇄ Blender MCP wiring).

## Security

* The Blender MCP server **requires** `BLENDER_MCP_TOKEN` — every request except
  `/health` must send `Authorization: Bearer <token>`.
* The Hermes WebUI is protected by dashboard basic auth
  (`HERMES_DASHBOARD_BASIC_AUTH_USERNAME` / `_PASSWORD`).
* `execute_blender_code` is the only arbitrary-code tool; it is reachable
  exclusively through the authenticated MCP endpoint.

## Licenses

* `hermes-agent` — MIT (Nous Research)
* `hermes-webui` — MIT (nesquena) — *not used; the official dashboard is used*
* Blender — GPL-3.0-or-later (bundled binary, redistributed in the image)
