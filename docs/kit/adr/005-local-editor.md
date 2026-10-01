# ADR 005 — A fourth editor that runs on the Mac

Date: 2026-10-01. Status: accepted.

## Decision

Add `local` as a fourth `ImageEditor`. It erases the old glyphs with OpenCV and redraws the new words in the installed font that best matches them. It runs as a Python subprocess in the OCR venv. It needs no key, no network, and no model weights. `mock` stays the code default so tests and CI are unchanged; `.env.example` selects `local`.

## Why

With no API key the product could only run the mock, which paints a labeled box. That proves the loop and nothing else. The builder asked for real edits on this Mac without a bill.

Local language models were the first idea and are the wrong tool. Qwen and DeepSeek under Ollama read and write text; they do not return an edited image. Ollama's experimental image generation never did image editing and was withdrawn in 0.32.6. A local diffusion editor (FLUX.2 klein, Qwen-Image-Edit) is a multi-gigabyte weight, which CONSTRAINTS.md rules out for v1, and on 24 GB it is slow and still garbles small text.

Redrawing text is a typesetting problem when the words are known. OCR already gives the old words and their box, so the editor can render those same words in every installed face, keep the one that overlaps the old glyphs best, and read size, color, and baseline off the pixels. The output spells the new words correctly every time, leaves every pixel outside the box untouched, and keeps the full resolution.

## Measured

`services/edit/eval.py` draws 275 scenes with a known answer (23 families, four sizes from 18 to 72 px, flat, gradient, and textured backgrounds, glyph edges softened by downscaling and JPEG) and compares the edit with the truth.

| | True font installed | True font hidden |
|---|---|---|
| Mean glyph overlap (soft IoU) | 0.72 | 0.45 |
| Cases at or above 0.5 | 91% | 41% |
| Exact family chosen | 87% | n/a |

The misses with the font installed are near-twins: Avenir for Avenir Next, Arial for Helvetica. Overlap is strict: a correct face one pixel off scores well under 1.

## Consequence

- `ADR 003` becomes one interface, four providers.
- The 1024 long-edge cap applies to paid providers, where it bounds cost. The local editor keeps the upload's size.
- Known limits, stated in the README: text on a busy photo is inpainted soft; rotated, curved, and perspective text is redrawn level; a replacement much longer than the original shrinks to fit rather than wrapping. A generative provider is the answer to those, behind the same interface.
- A local diffusion provider needs its own ADR and an explicit yes, because it reverses a `Never` in CONSTRAINTS.md.
