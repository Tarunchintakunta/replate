# Architecture — Replate

## Stack

| Piece | Choice |
|---|---|
| App | Next.js 15 App Router, React 19, TypeScript strict |
| UI | Tailwind CSS v4. Radix primitives only where a control needs a keyboard dialog or menu. No component marketplace. |
| Validation | Zod |
| Database | SQLite via Drizzle and `better-sqlite3` |
| Images | `sharp` for decode, resize, EXIF strip, PNG encode |
| OCR | Python 3.12 venv, `rapidocr-onnxruntime`, script `services/ocr/ocr.py` |
| Editor | Server-only interface. Implementations: mock, Gemini, WaveSpeed |
| Auth | Auth.js. Dev credentials provider always. Google provider only if env is set. |
| Payments | Stripe test mode, Checkout, one pack |
| Tests | Vitest and Playwright |
| Lint and format | Biome |
| Package manager | pnpm |
| Node | 22 |

Versions float to current stable at the time Claude scaffolds. Pin them in the lockfile. Do not invent a second framework.

## Processes on the Mac

```
Browser
  → Next.js (pnpm dev) on localhost
      → SQLite file in data/replate.db
      → image files in storage/
      → python services/ocr/ocr.py
      → HTTPS to Gemini or WaveSpeed only when that provider is selected
```

One terminal runs the app. OCR is a subprocess, not a daemon. If the subprocess fails, the user can still draw a box.

## Request path

1. `POST /api/images` accepts multipart. Check size, sniff the magic bytes, re-encode with sharp, write the file, insert the row.
2. `POST /api/images/:id/ocr` runs the sidecar and stores lines.
3. The page lets the user toggle lines and edit the replacement string.
4. `POST /api/generations` in one server function:
   - require a session
   - load the image and the selected lines
   - refuse if balance < 10
   - call the provider
   - on failure, write a generation row with status `failed` and do not touch the ledger
   - on success, write the PNG, insert the generation, insert a ledger debit, commit
5. `GET /api/generations/:id/file` streams the PNG. Only the owning user.

## Provider interface

```ts
export type Box = { x: number; y: number; width: number; height: number }

export type Replacement = {
  from: string
  to: string
  box: Box
}

export type EditInput = {
  png: Buffer
  width: number
  height: number
  replacements: Replacement[]
}

export type EditOutput = {
  png: Buffer
  provider: "mock" | "gemini" | "wavespeed"
  model: string
}

export interface ImageEditor {
  edit(input: EditInput): Promise<EditOutput>
}
```

`getEditor()` reads `EDITOR_PROVIDER`. Default `mock`. Unknown values throw at startup, not at click time.

### Prompt sent to a live model

Server-side only.

```
Edit this image. Change only the listed text. Keep font, color, size, perspective, lighting, and background. Do not alter anything else.

1. Inside the box x={x} y={y} width={width} height={height}, replace "{from}" with "{to}".
```

If `to` is empty, that line says: remove the text in the box and reconstruct the background. No new letters.

Do not send the user’s other files. Do not log the image bytes.

## Data

```
users
  id, email, name, created_at

sessions
  owned by Auth.js

images
  id, user_id, width, height, storage_key, created_at

ocr_lines
  id, image_id, text, confidence, x, y, width, height

generations
  id, user_id, image_id, provider, model, status, output_key, error, created_at

generation_replacements
  generation_id, ocr_line_id nullable, from_text, to_text, x, y, width, height

credit_ledger
  id, user_id, delta, reason, generation_id nullable, created_at
```

Balance is `sum(delta)` for the user. Never store a mutable balance column.

Reasons: `trial`, `debit_generation`, `stripe_pack`, `adjust`.

New user insert and the trial row of `+10` happen in the same transaction.

## Storage keys

`storage/originals/{imageId}.png`
`storage/generations/{generationId}.png`

The disk path is not the public URL.

## What the client is allowed to know

Public env: nothing secret. The UI may show the active provider name returned by `GET /api/health`, which reports `mock`, `gemini`, or `wavespeed` and whether the key is present as a boolean. It never returns the key.

## Commands Claude must wire

```
pnpm dev
pnpm test
pnpm exec playwright test
pnpm lint
pnpm build
pnpm db:migrate
python3 -m venv services/ocr/.venv
services/ocr/.venv/bin/pip install -r services/ocr/requirements.txt
```

`pnpm test` and Playwright do not call pip if the OCR unit test uses a fixture parser. The e2e test may stub OCR with a fixture response when `OCR_MODE=fixture`, and a separate test runs the real sidecar against a generated PNG when the venv exists. CI installs the venv.

## Repository layout

```
app/                     routes and server actions
components/              UI
db/                      schema and migrations
lib/editor/              interface, mock, gemini, wavespeed
lib/credits/
lib/images/
services/ocr/ocr.py
services/ocr/requirements.txt
e2e/
scripts/smoke-live.ts
docs/kit/                this kit, copied in issue 01
```

## Failure behavior

| Failure | User sees | Credits |
|---|---|---|
| Bad file type | “Use a PNG, JPG, or WebP.” | unchanged |
| OCR finds nothing | Empty list and the draw tool | unchanged |
| Balance under 10 | The generate button is disabled | unchanged |
| Provider HTTP error or timeout (60s) | The error text, try again | unchanged |
| Provider returns non-image | Same as timeout | unchanged |
| Success | Preview and download | −10 |
