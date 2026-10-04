# Local ReWords

Local-first app to detect, edit, replace, and preserve text inside images and PDFs. Translation is a later expansion, not part of this prototype.

## Problem

People need to change a word on a screenshot, a scan, or a PDF without redrawing the page. Hosted tools send the file to someone else's model. This prototype keeps the file, the OCR, and the inpainting on the machine that opens it.

## MVP

A person can:

1. Open the local web app.
2. Upload a PNG, JPEG, or PDF (including multi-page, text, scanned, and mixed files).
3. See detected text as selectable regions.
4. Replace one or more regions. The original pixels or PDF operators are removed, not painted over.
5. Undo, redo, reset, and compare before and after.
6. Export an image as PNG or JPG, or a PDF as PDF.

Flat backgrounds use fast OpenCV inpainting. Textured backgrounds can use LaMa. If LaMa is missing, the edit still completes in fast mode and the UI says so.

## Requirements

Functional:

- File-type detection from bytes, not the extension.
- Normalized text regions (`page`, `text`, `bbox`, `polygon`, `confidence`, `rotation`, `source`) so the UI does not depend on PaddleOCR.
- Image and scanned-page pipeline: mask, inpaint, render.
- Native PDF pipeline: redact the span and insert text, leaving other pages and vector drawings in place.
- Per-page kind for mixed PDFs.
- Edit history that never overwrites the upload.
- Explicit errors for unsupported files, corruption, empty text, missing models, bad replacement text, size limits, and export problems.

Non-functional:

- CPU-only is supported. An NVIDIA GPU is used when PyTorch or Paddle reports one. It is never required.
- No accounts, payments, cloud storage, or paid APIs.
- Models load once per process. OCR and rendered pages are cached. Only the edited page is regenerated.
- Uploads are size-limited, stored in an isolated directory, and old directories are deleted on startup.

## Acceptance

- A JPG can be uploaded, the text detected, one string replaced, and the export opened with the new text present and the old text gone.
- A 3-page text PDF can be edited on pages 2 and 3 without changing page 1, then exported as a PDF whose extracted text matches those edits.
- A 3-page scanned PDF can be edited the same way. The export is checked by rendering pages and running OCR, because a scanned export has no text layer.
- Automated tests cover the cases in `tests/`.

## Out of scope

Translation, accounts, billing, cloud deployment, exact font identification, cursive or handwriting, and full desktop publishing layout.

## Later

Swap the provider classes for another OCR engine, another inpainting model, S3, or a database. Add a local translation model only after replacement is solid. Broader scripts need OCR language packs and fonts that cover those glyphs. The bundled fonts are Latin.
