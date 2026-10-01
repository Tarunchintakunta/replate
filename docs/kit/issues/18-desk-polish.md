Title: Polish the desk and read headlines whole

Labels: replate, mvp

Spec: DESIGN.md, specs/SPEC-editor.md

## Why

A full pass over the running app found rough edges that the per-slice tests did not: a second picture needed a page reload, the phone header overflowed, a past result was stretched onto whatever picture was open, and OCR cut display type into words and dropped a first letter, which the local editor then could not replace cleanly.

## Acceptance

- An upload starts text detection by itself. `Detect Text` stays as a re-run, and detecting again keeps typed replacements and drawn boxes.
- `Choose another picture` under the stage swaps the picture without a reload. The file picker only offers PNG, JPG, and WebP.
- After a result, `Show original` and `Show result` toggle the preview.
- A past result opens on the picture it was made from, at that picture's shape.
- At 390px the header fits without horizontal scroll and the replace button stays in view while the list scrolls.
- With no credits, the bar links to the Credits page.
- OCR reads the image a second time at a coarse scale. A display-size line is corrected from it when the full-size box lost a glyph, and display-size words on one baseline are joined into one line. Small text is untouched.
- The local editor finds free room to the right of the old words on gradients, not only on flat color.

## Verify

```
pnpm test
RUN_OCR=1 pnpm test lib/ocr/sidecar.test.ts
pnpm exec playwright test
services/ocr/.venv/bin/python services/edit/eval.py
```

## Files

`src/components/*`, `src/app/api/generations/route.ts`, `services/ocr/ocr.py`, `services/edit/edit.py`, `lib/ocr/sidecar.test.ts`, `e2e/workflow.spec.ts`

## Out of this issue

New visual language. The tokens and type in DESIGN.md stay. Hosting the app anywhere but this Mac.
