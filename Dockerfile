# The hosted copy: Next.js, SQLite, and the Python sidecars in one container.
# See docs/kit/adr/006-hosted-copy.md. Data lives on a volume named by
# DATABASE_URL and STORAGE_PATH, never in the image.
FROM node:22-bookworm-slim

# python3 runs OCR and the local editor. libgl1 and libglib2.0-0 are what OpenCV links
# against, libgomp1 is for onnxruntime, libfribidi0 for Pillow's text layout.
# The fonts are the faces the local editor can match; a slim image ships none.
RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 python3-venv libgl1 libglib2.0-0 libgomp1 libfribidi0 \
      fonts-liberation fonts-dejavu-core fonts-croscore fonts-crosextra-carlito \
      fonts-crosextra-caladea fonts-urw-base35 fonts-roboto fonts-open-sans \
      fonts-lato fonts-inter \
    && rm -rf /var/lib/apt/lists/* \
    && corepack enable

WORKDIR /app

COPY services/ocr/requirements.txt services/ocr/
RUN python3 -m venv services/ocr/.venv \
    && services/ocr/.venv/bin/pip install --no-cache-dir -r services/ocr/requirements.txt

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

COPY . .
RUN pnpm build

# The host sets PORT.
CMD ["pnpm", "exec", "next", "start", "-H", "0.0.0.0"]
