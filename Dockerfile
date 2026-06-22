# ── Build ──────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime ────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# curl is used by the docker-compose healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for container security
RUN addgroup --system app && adduser --system --ingroup app app

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# hf_xet uses XET protocol and tries to write logs to $HOME — which is /nonexistent
# for the non-root app user. Uninstall it so huggingface_hub falls back to plain HTTP.
RUN pip uninstall hf_xet -y || true

# Bake the pre-downloaded fastembed ONNX model into the image.
# .fastembed_model.tar.gz was exported from a running container and committed to the repo.
# This avoids any runtime HuggingFace download and works fully offline.
ENV FASTEMBED_CACHE_PATH=/app/.fastembed_cache
COPY .fastembed_model.tar.gz /tmp/fastembed_model.tar.gz
RUN tar xzf /tmp/fastembed_model.tar.gz -C /tmp/ \
    && mv /tmp/fastembed_cache /app/.fastembed_cache \
    && chown -R app:app /app/.fastembed_cache \
    && rm /tmp/fastembed_model.tar.gz

# Copy source
COPY --chown=app:app . .

USER app

EXPOSE 8000

# PYTHONPATH ensures `from agent.state import ...` and `from app.config import ...` resolve correctly
ENV PYTHONPATH=/app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
