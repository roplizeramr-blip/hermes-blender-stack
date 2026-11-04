# Deployment on CranL

Both apps are deployed from **prebuilt GHCR images** (CranL's source-build
pipeline is currently broken: the build server never creates the `code/`
directory, so every `deploy_source` / `create_app` build fails with
`cd: .../code/: No such file or directory`).

> GHCR packages must be **public** (or the deploy must pass registry
> credentials) for the platform to pull them anonymously.

## 1. Blender MCP Server

```jsonc
// create_docker_app
{
  "name": "hermes-blender-mcp",
  "region": "netherlands-1",
  "image": "ghcr.io/roplizeramr-blip/hermes-blender-stack-blender-mcp:latest",
  "port": 8080,
  "volumes": ["/data"],
  "env": {
    "BLENDER_MCP_TOKEN": "<long random token>",
    "DATA_DIR": "/data"
  }
}
```

* Public URL: `https://hermes-blender-mcp-<suffix>.cranl.net`
* `GET /health` — open, returns `{"status":"ok",...}`
* `POST /mcp` — MCP Streamable HTTP, requires `Authorization: Bearer <token>`
* `/data` — persisted volume: `projects/ renders/ assets/ textures/ exports/ logs/ backups/`

## 2. Hermes AI Agent

```jsonc
// create_docker_app
{
  "name": "hermes-agent",
  "region": "netherlands-1",
  "image": "ghcr.io/roplizeramr-blip/hermes-blender-stack-hermes:latest",
  "port": 9119,
  "volumes": ["/opt/data"],
  "env": {
    "HERMES_DASHBOARD_BASIC_AUTH_USERNAME": "admin",
    "HERMES_DASHBOARD_BASIC_AUTH_PASSWORD": "<strong password>",
    "API_SERVER_KEY": "<long random key>",
    "BLENDER_MCP_URL": "https://hermes-blender-mcp-<suffix>.cranl.net/mcp",
    "BLENDER_MCP_TOKEN": "<same token as the Blender app>",
    "HERMES_PROVIDER": "openrouter",
    "HERMES_MODEL": "anthropic/claude-sonnet-4.5",
    "HERMES_PROVIDER_KEY_ENV": "OPENROUTER_API_KEY",
    "HERMES_PROVIDER_KEY": "<LLM provider API key>"
  }
}
```

* Public URL: `https://hermes-agent-<suffix>.cranl.net` → Hermes WebUI (dashboard)
* `/opt/data` — persisted volume = `$HERMES_HOME` (`config.yaml`, `.env`,
  `skills/`, `sessions/`, `state.db`, …)
* The boot hook `20-hermes-blender` merges `mcp_servers.blender` into
  `$HERMES_HOME/config.yaml` and seeds `$HERMES_HOME/skills/blender/`.

## 3. Verify the wiring

```bash
# Blender side
curl -s https://hermes-blender-mcp-<suffix>.cranl.net/health
curl -s -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1"}}}' \
     https://hermes-blender-mcp-<suffix>.cranl.net/mcp

# Hermes side (inside the container, or via the dashboard MCP page)
hermes mcp list
hermes mcp test blender
hermes skills list | grep blender
```

## 4. Restart-persistence check

`app_lifecycle(action="restart")` on both apps, then re-run the checks above:
the `/data` projects and the `/opt/data` Hermes home (config, skills, sessions)
must survive.
