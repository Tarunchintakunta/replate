# One container: Vite UI + FastAPI. Models download on first OCR, not at build.
FROM node:22-bookworm-slim AS ui
WORKDIR /ui
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend ./
RUN npm run build

FROM python:3.12-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 libgomp1 libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ \
 && pip install --no-cache-dir -r backend/requirements.txt

COPY backend backend
COPY fonts fonts
COPY models/checksums.json models/checksums.json
COPY scripts scripts
COPY --from=ui /ui/dist frontend/dist

ENV PYTHONUNBUFFERED=1
ENV REWORDS_CORS_ORIGINS=*
ENV FLAGS_use_mkldnn=0
ENV PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True
EXPOSE 8741

# LaMa in the image so hosted edits do not sit on "setup incomplete".
RUN python scripts/download_models.py --lama-only

CMD ["sh", "-c", "uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8741}"]
