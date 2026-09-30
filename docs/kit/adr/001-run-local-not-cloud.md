# ADR 001 — Run v1 on the Mac

Date: 2026-09-30. Status: accepted.

## Decision

Replate v1 runs on the Apple M5 Pro. Next.js, SQLite, files, and RapidOCR are local processes. The image editor is an HTTPS call to Gemini or WaveSpeed when a key exists. AWS and Google Cloud are not used.

## Why

The app is a thin loop around one model call. A cloud VM does not make OCR faster than this chip, and it adds IAM, billing, and a place for keys to leak. FLUX Kontext Pro is not a local model. Hosting a GPU to imitate it costs more per test than the API’s $0.04, and the open weights are the wrong quality bar.

Google Cloud is the same distraction with a different console. Gemini is used as an API, which does not require a GCP project for AI Studio keys.

## Later

When a second person needs the app, the first cloud step is object storage plus a small Node host. Still not a GPU. That step needs a new ADR and an explicit yes.
