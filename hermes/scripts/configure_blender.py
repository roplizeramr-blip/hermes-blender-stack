#!/usr/bin/env python3
"""Wire the Blender MCP server (and the LLM provider) into Hermes.

Executed from the s6 boot hook (``/etc/cont-init.d/20-hermes-blender``) with the
Hermes virtualenv interpreter, so it runs with the same YAML policy the agent
itself uses.

What it does
------------
1. ``$HERMES_HOME/config.yaml``  — merges ``mcp_servers.blender`` (streamable
   HTTP endpoint + ``Authorization: Bearer <token>``) and the ``model`` block
   (provider / default model / base_url).  Existing user settings are kept.
2. ``$HERMES_HOME/.env``          — writes the provider API key **only** when the
   key is not already configured, so a key entered later in the WebUI is never
   overwritten.

Environment (all optional)
--------------------------
BLENDER_MCP_URL           e.g. ``https://blender-mcp-xxxx.cranl.net/mcp``
BLENDER_MCP_TOKEN         bearer token for the Blender MCP server
BLENDER_MCP_ENABLED       "0" disables the MCP registration entirely
HERMES_PROVIDER           provider id: openrouter | openai | nous-api | gemini |
                          zai | kimi-coding | minimax | huggingface | nvidia |
                          xiaomi | arcee | ollama-cloud | deepinfra | custom ...
HERMES_MODEL              model id, e.g. ``anthropic/claude-sonnet-4.5``
HERMES_BASE_URL           provider base_url (only for custom/compatible endpoints)
HERMES_PROVIDER_KEY_ENV   env var name that holds the API key, e.g. OPENROUTER_API_KEY
HERMES_PROVIDER_KEY       the API key value (written into $HERMES_HOME/.env)
"""

from __future__ import annotations

import os
import pathlib
import sys

HOME = pathlib.Path(os.environ.get("HERMES_HOME", "/opt/data"))
CONFIG = HOME / "config.yaml"
ENV_FILE = HOME / ".env"

MCP_SERVER_NAME = "blender"


def log(message: str) -> None:
    print(f"[hermes-blender] {message}", flush=True)


# --------------------------------------------------------------------------- YAML
def _yaml_backend():
    """Return (load, dump) callables, preferring Hermes' own YAML 1.1 policy."""
    try:
        import hermes_yaml  # type: ignore

        def dump(data):
            return hermes_yaml.safe_dump(data)

        return hermes_yaml.safe_load, dump
    except Exception:
        pass
    try:
        import yaml  # type: ignore

        def dump(data):
            return yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=120)

        return yaml.safe_load, dump
    except Exception:
        pass
    from ruamel.yaml import YAML  # type: ignore

    y = YAML(typ="safe", pure=True)
    y.default_flow_style = False
    y.allow_unicode = True
    y.width = 120

    def dump(data):
        from io import StringIO

        buf = StringIO()
        y.dump(data, buf)
        return buf.getvalue()

    return y.load, dump


def read_config():
    load, _ = _yaml_backend()
    if not CONFIG.exists():
        return {}, load, _
    try:
        text = CONFIG.read_text(encoding="utf-8")
    except OSError as exc:
        log(f"cannot read {CONFIG}: {exc}")
        return {}, load, _
    try:
        data = load(text) if text.strip() else {}
    except Exception as exc:
        log(f"cannot parse {CONFIG} ({exc}) — leaving it untouched")
        return None, load, _
    if not isinstance(data, dict):
        data = {}
    return data, load, _


def write_config(data, dump) -> None:
    text = dump(data)
    tmp = CONFIG.with_suffix(".yaml.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, CONFIG)
    try:
        import pwd

        uid = pwd.getpwnam("hermes").pw_uid
        gid = pwd.getpwnam("hermes").pw_gid
        os.chown(CONFIG, uid, gid)
        os.chmod(CONFIG, 0o640)
    except Exception:
        pass
    log(f"wrote {CONFIG}")


# --------------------------------------------------------------------------- .env
def write_provider_key() -> None:
    key_env = (os.environ.get("HERMES_PROVIDER_KEY_ENV") or "").strip()
    key_value = (os.environ.get("HERMES_PROVIDER_KEY") or "").strip()
    if not key_env or not key_value:
        return
    existing = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    for line in existing.splitlines():
        if line.strip().startswith(f"{key_env}=") and line.split("=", 1)[1].strip():
            log(f"{key_env} already set in {ENV_FILE} — keeping it")
            return
    text = existing.rstrip("\n")
    if text:
        text += "\n"
    text += f"{key_env}={key_value}\n"
    ENV_FILE.write_text(text, encoding="utf-8")
    try:
        import pwd

        uid = pwd.getpwnam("hermes").pw_uid
        gid = pwd.getpwnam("hermes").pw_gid
        os.chown(ENV_FILE, uid, gid)
        os.chmod(ENV_FILE, 0o640)
    except Exception:
        pass
    log(f"wrote {key_env} into {ENV_FILE}")


# --------------------------------------------------------------------------- main
def main() -> int:
    HOME.mkdir(parents=True, exist_ok=True)
    data, load, dump = read_config()
    if data is None:
        return 1
    changed = False

    # --- Blender MCP server -------------------------------------------------
    if (os.environ.get("BLENDER_MCP_ENABLED") or "1").strip().lower() in ("0", "false", "no"):
        log("BLENDER_MCP_ENABLED=0 — skipping MCP registration")
    else:
        url = (os.environ.get("BLENDER_MCP_URL") or "").strip()
        token = (os.environ.get("BLENDER_MCP_TOKEN") or "").strip()
        if not url:
            log("BLENDER_MCP_URL not set — MCP server left untouched")
        else:
            servers = data.get("mcp_servers")
            if not isinstance(servers, dict):
                servers = {}
            # Keys validated against Hermes' MCP config reference
            # (website/docs/reference/mcp-config-reference.md):
            #   url / headers            -> HTTP server
            #   enabled / timeout / connect_timeout / keepalive_interval
            # Streamable HTTP is the default transport, so `transport` is omitted.
            entry = {
                "url": url,
                "enabled": True,
                "timeout": 1800,
                "connect_timeout": 60,
                "keepalive_interval": 60,
            }
            if token:
                entry["headers"] = {"Authorization": f"Bearer {token}"}
            existing = servers.get(MCP_SERVER_NAME)
            if existing != entry:
                servers[MCP_SERVER_NAME] = entry
                data["mcp_servers"] = servers
                changed = True
                log(f"registered MCP server '{MCP_SERVER_NAME}' -> {url} (auth: {'bearer' if token else 'none'})")
            else:
                log(f"MCP server '{MCP_SERVER_NAME}' already configured")

    # --- model provider -----------------------------------------------------
    model = data.get("model")
    if not isinstance(model, dict):
        model = {}
    provider = (os.environ.get("HERMES_PROVIDER") or "").strip()
    model_id = (os.environ.get("HERMES_MODEL") or "").strip()
    base_url = (os.environ.get("HERMES_BASE_URL") or "").strip()
    if provider and model.get("provider") != provider:
        model["provider"] = provider
        changed = True
        log(f"model.provider = {provider}")
    if model_id and model.get("default") != model_id:
        model["default"] = model_id
        changed = True
        log(f"model.default = {model_id}")
    if base_url and model.get("base_url") != base_url:
        model["base_url"] = base_url
        changed = True
        log(f"model.base_url = {base_url}")
    if model:
        data["model"] = model

    if changed or not CONFIG.exists():
        write_config(data, dump)
    else:
        log("config.yaml already up to date")

    write_provider_key()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # never break the container boot
        log(f"ERROR: {exc}")
        sys.exit(1)
