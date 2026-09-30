Title: Detect lines with RapidOCR

Labels: replate, mvp

Spec: specs/SPEC-ocr.md

## Why

The user should see the words that are already in the picture. A miss must still leave the draw tool.

## Acceptance

- `services/ocr/ocr.py` and a pinned `requirements.txt` for `rapidocr-onnxruntime`.
- `OCR_MODE=fixture` returns the `SALE` line and does not spawn Python.
- `OCR_MODE=rapid` spawns the venv, 10 second kill, Zod on stdout.
- `POST /api/images/:id/ocr` replaces lines for that image and only for the owner.
- Empty result and a crashed sidecar both leave the image up and the ledger unchanged.
- Parser unit tests use JSON strings. The sidecar test is gated on `RUN_OCR=1`.

## Verify

```
pnpm test lib/ocr/parse.test.ts
```

If the venv is installed, also:

```
RUN_OCR=1 pnpm test lib/ocr/sidecar.test.ts
```

## Files

`services/ocr/ocr.py`, `services/ocr/requirements.txt`, `lib/ocr/parse.ts`, `lib/ocr/run.ts`, `lib/ocr/parse.test.ts`, `lib/ocr/sidecar.test.ts`, `app/api/images/[id]/ocr/route.ts`, `components/LineList.tsx`

## Out of this issue

Replacing pixels. Do not call Gemini or WaveSpeed.
