# Spec: ocr

Module id: `ocr`. Depends on `storage`.

## Objective

Detect words already in the picture, on this Mac, with RapidOCR. If OCR fails or finds nothing, the user draws a box. Detection does not spend credits.

## Commands

```
python3 -m venv services/ocr/.venv
services/ocr/.venv/bin/pip install -r services/ocr/requirements.txt
pnpm test lib/ocr/parse.test.ts
RUN_OCR=1 pnpm test lib/ocr/sidecar.test.ts
```

## Project structure

```
services/ocr/ocr.py
services/ocr/requirements.txt     rapidocr-onnxruntime pinned
lib/ocr/parse.ts                  Zod for the sidecar JSON
lib/ocr/run.ts                    spawn the venv python, or the fixture
lib/ocr/parse.test.ts
app/api/images/[id]/ocr/route.ts
```

## Behavior

`ocr.py` takes one argument, the PNG path. It prints one JSON object to stdout and nothing else:

```json
{ "lines": [{ "text": "SALE", "confidence": 0.9, "x": 10, "y": 12, "width": 80, "height": 24 }] }
```

Coordinates are pixels of that PNG, origin top-left. On failure it exits non-zero and prints one line to stderr. No image bytes on stdout.

`POST /api/images/:id/ocr` runs detection for the owner, replaces previous `ocr_lines` for that image, and returns the lines.

`OCR_MODE=rapid` uses the sidecar. `OCR_MODE=fixture` does not spawn Python. It returns one line, text `SALE`, box `{ x: 8, y: 8, width: 48, height: 16 }`, confidence `1`. Tests and Playwright use `fixture`. CI’s OCR job sets `RUN_OCR=1` and `OCR_MODE=rapid` for `sidecar.test.ts` only.

The Node side kills the process at 10 seconds. A timeout is an error the UI shows as “Could not read text. Draw a box.” The image stays.

Empty `lines` is success. The list is empty and the draw tool is the next step.

## Code style

Zod:

```ts
const Line = z.object({
  text: z.string().max(200),
  confidence: z.number().min(0).max(1),
  x: z.number().int().nonnegative(),
  y: z.number().int().nonnegative(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
})
```

Drop lines whose box falls outside the image.

## Testing strategy

- Parser tests use a recorded JSON string. They do not download models.
- `sidecar.test.ts` skips unless `RUN_OCR=1`. It generates a PNG with sharp that contains the word `SALE` in a plain sans at a large size, and asserts at least one line comes back. OCR is allowed to miss stylized type. This fixture is plain on purpose.
- Playwright uses `OCR_MODE=fixture` so the suite does not depend on the model download.

## Boundaries

- Always: treat stdout as untrusted and parse with Zod.
- Ask first: committing ONNX weights. Read the RapidOCR license before vendoring. If the CI download is blocked, stop and report. Do not skip the test.
- Never: send the image to a cloud OCR API in v1. Never log the PNG.

## Success criteria

- Fixture mode returns the known line with no Python.
- Rapid mode, when the venv exists, returns at least one line for the plain `SALE` PNG in under 5 seconds on this Mac.
- A crash of `ocr.py` does not change the ledger and does not clear the image.

## Open questions

None.
