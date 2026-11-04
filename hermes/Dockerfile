# Hermes AI Agent — WebUI + MCP client + Blender skills
#
# Base image: the official NousResearch Hermes Agent image.
#   * Hermes Agent core (Python 3.14 venv, MCP client, skills engine, tools)
#   * The built-in web dashboard (React) served by `hermes dashboard`:
#       /  ChatPage · McpPage · SkillsPage · ModelsPage · FilesPage · SessionsPage
#       + full i18n including Arabic (ar.ts)
#   * s6-overlay supervision tree (main hermes process, dashboard, per-profile gateways)
#
# This image adds:
#   * 10 Blender skills (agentskills.io SKILL.md) baked in and seeded into
#     $HERMES_HOME/skills/blender/ on every boot.
#   * A boot hook that wires the Blender MCP server into $HERMES_HOME/config.yaml
#     (mcp_servers.blender) and seeds the LLM provider settings.
#
# Public port: 9119 (Hermes dashboard / WebUI).

FROM nousresearch/hermes-agent:latest

LABEL maintainer="roplizeramr-blip"
LABEL description="Hermes AI Agent (WebUI + MCP + Blender skills) for the Hermes-Blender stack"

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HERMES_HOME=/opt/data \
    HERMES_WRITE_SAFE_ROOT=/opt/data \
    HERMES_DASHBOARD=1 \
    HERMES_DASHBOARD_HOST=0.0.0.0 \
    HERMES_DASHBOARD_PORT=9119 \
    HERMES_DASHBOARD_BASIC_AUTH_USERNAME=admin \
    API_SERVER_ENABLED=true \
    API_SERVER_HOST=0.0.0.0 \
    HERMES_BLENDER_SKILLS_DIR=/opt/hermes-blender/skills/blender

# The 10 Blender skills are ALSO baked into the image's bundled-skills tree
# (/opt/hermes/skills/<category>/<name>/SKILL.md) so Hermes' own bundled-skill
# sync installs them into $HERMES_HOME/skills/blender/<name>/ — exactly like the
# 44 skills that ship with the agent. The second copy under
# /opt/hermes-blender/skills is the fallback the boot hook seeds by hand.
COPY skills/blender/ /opt/hermes/skills/blender/
COPY skills/blender/ /opt/hermes-blender/skills/blender/
COPY hermes/scripts/configure_blender.py /opt/hermes-blender/configure_blender.py

# s6-overlay runs /etc/cont-init.d/* before the supervised services start.
# 20- runs after the image's own 01-hermes-setup (config seeding, skills sync).
COPY --chmod=0755 hermes/cont-init.d/20-hermes-blender /etc/cont-init.d/20-hermes-blender

RUN chmod 0755 /opt/hermes-blender/configure_blender.py && \
    /opt/hermes/.venv/bin/python -m py_compile /opt/hermes-blender/configure_blender.py && \
    mkdir -p /opt/data/skills/blender && \
    ls -1 /opt/hermes/skills/blender && \
    ls -1 /opt/hermes-blender/skills/blender

EXPOSE 9119 8642

# `gateway run` starts the Hermes gateway (API server on 8642, cron, messaging);
# the dashboard runs as its own supervised service because HERMES_DASHBOARD=1.
CMD ["gateway", "run"]
