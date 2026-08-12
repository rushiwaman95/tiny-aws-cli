# ---------- Build stage ----------
FROM python:3.11-slim AS builder
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build

# CPU-only PyTorch (saves ~2-4 GB vs CUDA wheels)
# --no-compile skips .pyc bytecode caches at install time (they're
# just dead weight in a container that's rebuilt from scratch)
RUN pip install --no-cache-dir --no-compile --prefix=/install torch \
        --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir --no-compile --prefix=/install transformers

# Strip C++/CUDA headers, bundled test suites, and legacy Caffe2 code
# that ship with torch but a pure inference server never touches.
# Safe for the standard torch + transformers CPU path - smoke-test
# the built image before relying on this.
RUN find /install -type d \( -name "test" -o -name "tests" \) -exec rm -rf {} + \
 && rm -rf /install/lib/python*/site-packages/torch/include \
 && rm -rf /install/lib/python*/site-packages/torch/utils/bottleneck \
 && rm -rf /install/lib/python*/site-packages/torch/utils/tensorboard \
 && rm -rf /install/lib/python*/site-packages/caffe2

# ---------- Runtime stage ----------
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    HF_HUB_DISABLE_TELEMETRY=1
WORKDIR /app

# Bring in only the installed packages, nothing else
COPY --from=builder /install /usr/local
COPY app.py .
# Before building: audit this folder for leftover training artifacts
# (optimizer.pt, scheduler.pt, old checkpoint-*/ dirs) and duplicate
# weight formats. Keep only what inference actually loads.
COPY supra-mini-aws-final ./supra-mini-aws-final

# Security: run as non-root
RUN useradd --create-home appuser \
 && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1
CMD ["python", "app.py", "--serve"]
