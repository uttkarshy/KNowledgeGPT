# syntax=docker/dockerfile:1

# ---------- Builder stage: compile wheels, keep build tools out of final image ----------
FROM python:3.12-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Final stage ----------
FROM python:3.12-slim

# System dependencies actually needed at RUNTIME (see SYSTEM_DEPENDENCIES.md):
#   - tesseract-ocr + tesseract-ocr-hin: OCR for scanned PDFs/images (English + Hindi)
#   - libgl1: required by some PyMuPDF/Pillow image codecs
#   - curl: used by the container healthcheck below
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    libgl1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — never run the app as root in a container.
RUN groupadd -r knowledgegpt && useradd -r -g knowledgegpt knowledgegpt

WORKDIR /app

COPY --from=builder /root/.local /home/knowledgegpt/.local
COPY . .
RUN chmod +x /app/entrypoint.sh

RUN chown -R knowledgegpt:knowledgegpt /app /home/knowledgegpt
USER knowledgegpt

ENV PATH=/home/knowledgegpt/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

# Default command runs the API. The Celery worker service in docker-compose
# overrides this with `celery -A app.workers.celery_app worker` instead —
# same image, different process, per the spec's "one image, multiple
# services" pattern.
CMD ["gunicorn", "app.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "120", \
     "--access-logfile", "-", "--error-logfile", "-"]
