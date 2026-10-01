Title: Edit on this Mac with a local editor

Labels: replate, mvp

Spec: specs/SPEC-editor.md, adr/005-local-editor.md

## Why

Without an API key the only editor is the mock, which paints a white box. The product has to make a real edit on this Mac with no key and no cloud bill.

## Acceptance

- `EDITOR_PROVIDER=local` selects `LocalEditor`. `mock` stays the code default so tests and CI do not change.
- `services/edit/edit.py` runs in the OCR venv. No new pip or npm dependency.
- For each box: the old glyphs are erased, the new words are drawn in the closest installed font at the same size, color, and baseline. An empty replacement only erases.
- A drawn box with no known old text still works: the sidecar reads the box itself.
- Pixels outside the edited box do not change. The output keeps the input's pixel size.
- Missing venv throws with the install command. A sidecar failure is a failed generation, so credits are unchanged.
- `services/edit/eval.py` scores the editor against scenes with a known answer and exits 1 under a mean glyph overlap of 0.5.
- Health pill says `Local editor`.

## Verify

```
pnpm test lib/editor/local.test.ts
services/ocr/.venv/bin/python services/edit/eval.py
services/ocr/.venv/bin/python services/edit/eval.py --held-out
```

## Files

`services/edit/edit.py`, `services/edit/eval.py`, `lib/editor/local.ts`, `lib/editor/local.test.ts`, `lib/editor/index.ts`, `src/components/TopBar.tsx`, `.env.example`, `README.md`, `.github/workflows/ci.yml`

## Out of this issue

Diffusion weights on the Mac. Rotated, curved, or perspective text. Wrapping a long replacement onto a second line. Credits and rate limits, which are issue 17.
