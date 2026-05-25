# AgentDrive — self-host image
#
# Multi-stage build. Final image is python:3.12-slim + agentdrive installed
# from the source tree. Runs as a non-root user (uid 10001, "drive") and
# stores all state under /var/lib/agentdrive. Mount that path to a host
# volume to persist genomes, caps, audit log.

# ─── builder ──────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --upgrade pip \
 && pip wheel --wheel-dir /wheels .

# ─── runtime ──────────────────────────────────────────────────────────────
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AGENTDRIVE_HOME=/var/lib/agentdrive \
    PORT=8421

RUN apt-get update \
 && apt-get install -y --no-install-recommends tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd --system --gid 10001 drive \
 && useradd  --system --uid 10001 --gid drive --home-dir /home/drive --create-home drive \
 && mkdir -p /var/lib/agentdrive \
 && chown drive:drive /var/lib/agentdrive

COPY --from=builder /wheels /tmp/wheels
RUN pip install --no-cache-dir /tmp/wheels/*.whl \
 && rm -rf /tmp/wheels

USER drive
WORKDIR /home/drive

EXPOSE 8421

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8421\")}/healthz').read()" || exit 1

ENTRYPOINT ["tini", "--"]
CMD ["sh", "-c", "agentdrive web --host 0.0.0.0 --port ${PORT}"]
