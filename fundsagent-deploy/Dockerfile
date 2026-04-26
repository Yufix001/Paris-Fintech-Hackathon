# FundsAgent — single-file webapp · Cloud Run target
# Build:  docker build -t fundsagent:latest .
# Deploy: bash scripts/deploy.sh   (wraps gcloud run deploy --source .)

FROM python:3.11-slim-bookworm

# OS-level deps for PDF/PPTX extraction libs (pdfplumber relies on a couple of
# native libraries via cffi). Keep the image lean.
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Pin everything so the demo is reproducible.
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
        fastapi==0.115.0 \
        uvicorn==0.30.0 \
        httpx==0.27.0 \
        python-multipart==0.0.9 \
        pypdf==4.3.1 \
        python-pptx==1.0.2 \
        pdfplumber==0.11.4

COPY fundsagent.py /app/
# Copy the Lovable-based frontend (served at /) and the demo pitch deck (served at /static/)
COPY frontend/index.html /app/frontend/index.html
COPY NeuroLedger_PitchDeck.pptx /app/NeuroLedger_PitchDeck.pptx
COPY static/ /app/static/
COPY data/ /app/data/

# Cloud Run injects $PORT at runtime (default 8080). fundsagent.py reads it
# at the bottom of main() with fallback to 8000 for local dev.
ENV PORT=8080
EXPOSE 8080

# Tiny in-image healthcheck for local docker run; Cloud Run uses /api/health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl --fail --silent http://localhost:${PORT}/api/health || exit 1

CMD ["python", "fundsagent.py"]

