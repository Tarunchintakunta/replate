# Capability map — Replate

| Module id | Responsibility | Depends on |
|---|---|---|
| shell | App frame, tokens, empty workspace | — |
| storage | SQLite, files on disk, image records | — |
| workspace | Upload, preview, line list, draw box | shell, storage |
| ocr | RapidOCR sidecar, line schema | storage |
| editor | Provider interface, mock, Gemini, WaveSpeed | storage |
| credits | Ledger, trial grant, charge on success | storage |
| generation | Orchestrate OCR result + editor + credits + download | workspace, ocr, editor, credits |
| auth | Dev session, optional Google | storage |
| billing | Stripe test pack that adds credits | auth, credits |
| proof | Playwright, CI, secret scan | generation |

Build order: shell and storage → workspace → ocr, editor, credits → generation → auth → billing, and proof wraps generation.

No cycles. Billing never calls the editor. The editor never reads Stripe.
