# ADR 006 — One container for a hosted copy

Date: 2026-10-02. Status: accepted. The database and sign-in rows are superseded by ADR 007.

## Decision

Replate gets a `Dockerfile` that runs the whole app in one container: Next.js, SQLite, and the Python OCR and local editor sidecars. SQLite and the image files live on a mounted volume named by `DATABASE_URL` and `STORAGE_PATH`, never in the image. Railway is the host the builder chose; `railway.json` points it at the `Dockerfile` and at `/api/health`.

The Mac stays the main environment. Nothing in the code path changes: the same `pnpm build` and `next start` run inside the container.

## Why

The builder asked for a hosted link that works end to end. ADR 001 named the first cloud step as "a small Node host" and required a new ADR and an explicit yes; this is that step, and the yes came in chat on 2026-10-02.

Vercel alone cannot run this app. Its functions have no disk that survives a request, so SQLite and `storage/` would vanish, and it cannot keep a Python venv beside the Node runtime for OCR and the local editor. A container host keeps every part as it is. Vercel can still serve the public address by forwarding every path to the container.

## Hosted settings

| Variable | Value on the host |
|---|---|
| `APP_URL` | the public `https://` address. Anything but `http://localhost:3000` turns the passwordless local button off |
| `AUTH_SECRET` | a long random string, set once |
| `AUTH_GOOGLE_ID`, `AUTH_GOOGLE_SECRET` | the only sign-in on a hosted copy |
| `DATABASE_URL`, `STORAGE_PATH` | `/data/replate.db`, `/data/storage` on the volume |
| `EDITOR_PROVIDER` | `local`, or `gemini` with `GEMINI_API_KEY` |
| `OCR_MODE` | `rapid` |

## Measured

The image is 2.4 GB. In a local run of the image, the full loop passed over HTTP: sign in, upload, OCR, edit, download, refill. The balance and the result survived a container restart.

The container has Linux fonts, not the Mac's: Liberation and Croscore (metric twins of Arial, Times New Roman, and Courier New), URW base35 (twins of Helvetica, Times, Palatino, and others), Carlito, Caladea, DejaVu, Roboto, Open Sans, Lato, and Inter. `eval.py` there runs only the 25 cases whose family is installed: 0.79 mean overlap, 96% of cases at or above 0.5. A picture set in a Mac-only face gets its nearest Linux twin, so the hosted copy matches fonts less well than the Mac does.

## Consequence

- A hosted copy has no free refill. Credits beyond the trial go through Stripe.
- Container build time and size are the cost of keeping the local editor. A hosted copy that runs only `gemini` could drop Python, but would lose OCR too.
- CI does not build the image. Add that job if the `Dockerfile` starts to drift.
