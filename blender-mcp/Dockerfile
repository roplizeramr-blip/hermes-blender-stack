# Blender MCP - Debian 12 "bookworm" edition
# nginx (public :8080) -> uvicorn/MCP (:8000) -> Blender bridge (127.0.0.1:9876)
FROM debian:bookworm-slim

ARG BLENDER_VERSION=4.5.15
ARG DEBIAN_CODENAME=bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    DEBIAN_CODENAME=${DEBIAN_CODENAME} \
    DATA_DIR=/data \
    MCP_PORT=8000 \
    BLENDER_BRIDGE_PORT=9876 \
    NGINX_PORT=8080

# ---------------------------------------------------------------------------
# System packages. The list is intentionally generous: Blender needs a set of
# X/GL libraries even when running headless. If a name does not exist on this
# Debian release the install is retried with only the packages that do exist,
# so the same Dockerfile keeps working across Debian versions.
# ---------------------------------------------------------------------------
RUN set -eux; \
    apt-get update; \
    pkgs="ca-certificates curl xz-utils gzip procps tini \
          nginx python3 python3-venv python3-pip \
          libgl1 libglu1-mesa libglib2.0-0 libsm6 libice6 libxi6 libxrender1 libxext6 \
          libxkbcommon0 libegl1 libdbus-1-3 libxfixes3 libxcursor1 libxxf86vm1 \
          libwayland-client0 libxrandr2 libxinerama1 libxcomposite1 libharfbuzz0b \
          libgomp1 libtbb12 libfreetype6 libfontconfig1"; \
    if ! apt-get install -y --no-install-recommends $pkgs; then \
        echo ">> some packages are unavailable on this release, retrying with the subset that exists"; \
        dpkg --configure -a || true; \
        apt-get -f install -y || true; \
        avail=""; \
        for p in $pkgs; do \
            if apt-cache show "$p" >/dev/null 2>&1; then avail="$avail $p"; fi; \
        done; \
        echo ">> installing:$avail"; \
        apt-get install -y --no-install-recommends $avail; \
    fi; \
    rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Blender LTS (4.5.15) - official linux-x64 build, baked into the image.
# ---------------------------------------------------------------------------
RUN set -eux; \
    curl -fSL --retry 5 --retry-delay 5 --retry-all-errors \
        "https://download.blender.org/release/Blender4.5/blender-${BLENDER_VERSION}-linux-x64.tar.xz" \
        -o /tmp/blender.tar.xz; \
    mkdir -p /opt; \
    tar -xJf /tmp/blender.tar.xz -C /opt; \
    mv "/opt/blender-${BLENDER_VERSION}-linux-x64" /opt/blender; \
    rm -f /tmp/blender.tar.xz; \
    /opt/blender/blender --version

# ---------------------------------------------------------------------------
# Python environment for the MCP server
# ---------------------------------------------------------------------------
RUN set -eux; \
    python3 -m venv /opt/venv; \
    /opt/venv/bin/pip install --no-cache-dir --upgrade pip; \
    /opt/venv/bin/pip install --no-cache-dir "mcp>=1.10,<2" "uvicorn>=0.30" "starlette>=0.37"

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN /opt/venv/bin/pip install --no-cache-dir -r /app/requirements.txt

COPY mcp_server.py blender_bridge.py entrypoint.sh /app/
COPY nginx.conf /etc/nginx/nginx.conf
COPY index.html /usr/share/nginx/html/index.html

# Fail the build instead of the container when the Python sources do not
# compile on the image interpreter (Debian bookworm ships Python 3.11).
RUN /opt/venv/bin/python -m py_compile /app/mcp_server.py /app/blender_bridge.py && \
    echo "python sources compile cleanly"

RUN set -eux; \
    chmod +x /app/entrypoint.sh; \
    rm -f /etc/nginx/sites-enabled/default; \
    mkdir -p /data/projects /data/renders /data/assets /data/textures /data/exports /data/logs /data/backups; \
    nginx -t

ENV PATH="/opt/venv/bin:$PATH"

EXPOSE 8080


CMD ["/usr/bin/tini", "--", "/app/entrypoint.sh"]
