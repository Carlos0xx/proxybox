FROM python:3.13-slim-bookworm

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

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -e .

ENV PROXYBOX_CONFIG=/etc/proxybox/config.yaml

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
