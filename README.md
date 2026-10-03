This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, run the development server:

```bash
npm run dev
# or
yarn dev
# or
pnpm dev
# or
bun dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## OCR and local editor setup

Detect Text runs a local RapidOCR sidecar, and `EDITOR_PROVIDER=local` runs
`services/edit/edit.py` in the same venv. Install it once (Python 3.12 recommended):

```bash
python3 -m venv services/ocr/.venv
services/ocr/.venv/bin/pip install -r services/ocr/requirements.txt
cp .env.example .env
```

`OCR_MODE` defaults to `rapid`. Set `OCR_MODE=fixture` only for tests, which returns a canned line.

## Editors

| `EDITOR_PROVIDER` | What it does | Needs |
|---|---|---|
| `local` | Erases the old words with OpenCV and redraws the new ones in the closest installed font, at full resolution. Nothing outside the edited box changes. | the venv above |
| `mock` | Paints a labeled box. For tests and CI. | nothing |
| `gemini` | Sends the image to Gemini for a generative edit. | `GEMINI_API_KEY` |
| `wavespeed` | Sends the image to FLUX Kontext Pro. | `WAVESPEED_API_KEY` |

The local editor is strongest on screenshots, documents, and flat or gradient artwork.
Text on a busy photo, on a curve, or in perspective is where a generative provider does better.

## Credits

`pnpm dev` listens on this Mac only (127.0.0.1), because the local sign-in has no password.

A new user gets 10 trial credits and an image costs 10. On `http://localhost:3000` the
passwordless local user can add 100 more for free from the Credits page. Everyone else
buys the pack through Stripe test mode. The 10-attempts-per-hour limit guards paid keys,
so it does not apply to the local editor.

## Benchmark

Measure the local editor against scenes with a known answer:

```bash
services/ocr/.venv/bin/python services/edit/eval.py            # every font installed
services/ocr/.venv/bin/python services/edit/eval.py --held-out # the true font hidden
```

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Run in a container

The `Dockerfile` runs the whole app, OCR and the local editor included. Keep the database and images on a volume:

```bash
docker build -t replate .
docker run -p 3000:3000 -e PORT=3000 -e APP_URL=https://your.domain -e AUTH_SECRET=change-me -e DATABASE_URL=postgres://... -e STORAGE_PATH=/data/storage -e EDITOR_PROVIDER=local -v replate-data:/data replate
```

A hosted copy needs `APP_URL` set to its `https://` address and `DATABASE_URL` set to a Neon `postgres://` URL. People sign up with a username and password; the local button only exists on `http://localhost:3000`. Railway reads `railway.json`. Vercel cannot run the app itself because it has no disk and no Python beside Node. See `docs/kit/adr/006-hosted-copy.md`.
