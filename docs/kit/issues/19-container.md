Title: Run Replate in one container

Labels: replate, mvp

Spec: adr/006-hosted-copy.md

## Why

The builder wants a hosted link. The app needs a disk and a Python venv beside Node, which a container host gives and Vercel functions do not.

## Acceptance

- `docker build .` succeeds from a clean clone.
- The container serves the full loop on `PORT`: sign in, upload, detect, replace, download.
- SQLite and images live under a mounted volume and survive a restart.
- OCR and the `local` editor run inside the container, with Linux fonts to match against.
- `railway.json` builds from the `Dockerfile` and health-checks `/api/health`.
- No secret is baked into the image. `.dockerignore` keeps `.env`, `data/`, and `storage/` out.

## Verify

```
docker build -t replate .
docker run -p 3200:3200 -e PORT=3200 -e AUTH_SECRET=... -e DATABASE_URL=/data/replate.db -e STORAGE_PATH=/data/storage -e EDITOR_PROVIDER=local -v replate-data:/data replate
curl localhost:3200/api/health
```

## Files

`Dockerfile`, `.dockerignore`, `railway.json`, `adr/006-hosted-copy.md`, `README.md`

## Out of this issue

Creating the Railway project, its volume, and its variables. Google sign-in keys. A Vercel address in front of the container.
