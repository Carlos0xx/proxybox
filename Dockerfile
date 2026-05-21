# Base image pinned to a specific patch — Dependabot's `docker`
# ecosystem watches this line and opens a PR when 3.13.x bumps. Floating
# `:3.13-slim-bookworm` would pull a fresh image silently on every build,
# which is the supply-chain hazard we want to avoid.
FROM python:3.13.13-slim-bookworm

# Runtime essentials:
# - openssl: bootstrap generates the Hy2 self-signed cert
# - sqlite3: convenient for inspection inside the container
# - curl: bootstrap uses it to detect public IP
# - ca-certificates: TLS handshakes (ifconfig.me, etc.)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        openssl sqlite3 curl ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/proxybox

# Layer pyproject + README first so dependency installs cache independently of source edits
COPY pyproject.toml README.md ./

# Source last
COPY app/ ./app/
COPY bot/ ./bot/
COPY static/ ./static/
COPY deploy/docker/ ./deploy/docker/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e . \
    && chmod +x deploy/docker/*.sh

ENV PROXYBOX_CONFIG=/etc/proxybox/config.yaml

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
