# FinPilot HomeLoan API. Build from the REPO ROOT so the synthetic personas are baked in:
#   docker build -f backend/Dockerfile -t finpilot-homeloan-api .
#   docker run -p 8000:8000 -e DEMO_MODE=1 finpilot-homeloan-api
# Optional OCR: --build-arg WITH_OCR=1
FROM python:3.12-slim
ARG WITH_OCR=0
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    DEMO_MODE=1 DATA_DIR=/app/backend/.data PERSONAS_DIR=/app/data/personas PORT=8000
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 \
    $( [ "$WITH_OCR" = "1" ] && echo "libgl1 libglib2.0-0" ) && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt backend/requirements-ocr.txt ./
RUN pip install -r requirements.txt && if [ "$WITH_OCR" = "1" ]; then pip install -r requirements-ocr.txt; fi
COPY backend/ /app/backend/
COPY data/ /app/data/
RUN useradd -m -u 1000 app && mkdir -p /app/backend/.data && chown -R app /app/backend/.data
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/api/health')"
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
