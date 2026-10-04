# Handoff: make a text edit look unedited

You are taking over Local ReWords, a local clone of ReWords.ai. The app already uploads a PNG, JPEG, or PDF, detects text, removes the old strokes, draws a replacement, previews it, and exports. That shell works. The replacement still looks edited. That is the only job.

The owner’s last instruction, verbatim:

> Font is changed shape boldness colour etc are bieng changed in tour video it self your claming 70+ accuracy rhe matter is not about text changing its about text changing that shouldn’t like it was changed or manipulated
>
> Check rewords ai it literally does 90+
>
> Buddy it is not at all matching your trying to hard coded them i dont to hardcode them i eant accurate and better output
>
> Lets use gpu and paid stuff if requ etc i want zip with handoff file to claude

GPU and paid APIs are now allowed. CPU-only and “no paid APIs” were earlier constraints. They lost. Use a GPU model or a paid image API when that is what it takes for the new word to keep the original face, weight, color, outline, spacing, and orientation.

## The bar

A replacement succeeds only when a person cannot see that the line was rewritten. Same letter shapes, same boldness, same color, same outline or shadow, same blur and grain, same rotation. Unchanged characters must stay the original pixels.

A match score of 70, 80, or 100 is not success. The UI currently prints “Visual match NN%” after Apply. Those numbers were shown on a video the owner rejected, because the letters were visibly a different shape, weight, and color. Do not tune `ACCEPT` or `FLOOR` to print a higher percent. Do not show a percent as the claim.

ReWords.ai’s own description of the bar (https://rewords.ai/replace-text-in-image/ and https://rewords.ai/edit-text-in-image-same-font/):

- Detect the line, erase it, reconstruct the background by inpainting.
- Read the original typography from the picture. They say the exact font file is not recovered.
- Redraw the new string at the original height, weight, color, tracking, alignment, and effects (shadow, gradient, texture).
- They do not squash a longer or shorter word into the old box. Their UI warns that a length change can force a size or spacing change.
- They often emit two renders and keep the one that looks less edited.

Same-text rewrite of a line should reconstruct that line. A different word cannot be pixel-identical, but its print (stroke width, color distance, edge softness, outline) must match, and each letter must keep its natural aspect ratio.

## Do not do this

- Do not hardcode replacement words, anagrams, or per-image branches. The rejected demo only used words the page could already spell (`FEST`, `DATE`, `MEAL`, `MATTER`, `COLD`) because the code refused every other string. The owner called that hardcoding.
- Do not anisotropically scale a new word to the old span width. That is the main reason shape and boldness change.
- Do not repaint a letter as one median color when the original has an outline, a second color, or a shadow.
- Do not refuse an edit just because one letter was never seen on the page, and do not substitute a generic Liberation or Barlow face and call it a match. A thermal receipt’s best bundled-font overlap was about 27%.
- Do not claim the bundled-font IoU, the glyph-bank coverage, or `match_score` as the result. Judge the pixels.
- Do not trust an image-caption model on these crops. It has misread the words. Trust OCR, column widths, stroke width, and color distance.
- Do not loosen `tests/test_print_style.py`. Its edge-energy band (0.7 to 1.3) and ink-median band (14 gray levels) were set before the run. If a change fails them, the print got sharper or shifted color.

## Why the current paint looks manipulated

`backend/app/rendering/print_style.py` is the raster path that actually ships.

`preserve_line` copies columns that SequenceMatcher marks equal, so the prefix of “EVERY LITTLE HELPS” → “EVERY LITTLE COUNTS” has mean absolute difference 0. That part is correct. Keep it.

The changed span goes through `_paint_chunk`. That function renders page glyphs at the donor ink height, then `cv2.resize`s the alpha to `(target_w, target_h)` where `target_w` is the entire donor span width. A shorter word is stretched. A longer word is squashed. Stroke thickness changes on one axis. That is the “shape and boldness changed” bug.

`_imprint` then paints that mask with one median BGR color, a searched Gaussian blur, a row gain, and noise. A yellow fill with a black outline becomes flat yellow. A colored shadow is dropped. The new word looks cleaner than the original.

`preserve_line` returns `None` unless every introduced character already exists in the glyph bank. `backend/app/image/editing.py` is stricter: `use_glyphs` is true only when `bank.missing_chars(new_text) == ""` for the whole new string. Otherwise `_refuse_weak_font` raises `FONT_MATCH_LOW` when bundled-font confidence is under 0.34. The frontend repeats the gate: `frontend/src/App.tsx` sets `blocked` when any draft letter is missing from `page_glyphs` and `font_confidence < 0.45`, and it disables Apply. That is why the demo could only show anagrams.

`backend/app/rendering/glyph_bank.py` cuts letters from OCR lines with confidence ≥ 0.85. Thin full-height strokes (the letter I) are kept. `_binarize` is grayscale Otsu, so a green word on stripes and a red word with a blue shadow still fail to segment. Color is estimated in `backend/app/image/style.py` by 2-means against the ring background; a mask full of stripe background returns near-white.

`backend/app/rendering/visual_match.py` detects a dark-ink shadow or outline and scores height, color, weight, tracking, position, opacity, angle, and effects. `score_against().total` is what the UI prints. `preserve_line` returns even when that score is under 0.84, which is how the outline and rotated cases were shown at 80%. The score is not a gate you should raise. It is the wrong metric.

Neural editors (SRNet, MOSTEL, DeepVecFont) were skipped earlier because the machine had no GPU and the weights were large. That skip is no longer justified.

## What already works and should stay

- Upload, magic-byte checks, 25 MB limit, isolated storage, original file never overwritten.
- PaddleOCR behind `OCRProvider`. Native PDF text via PyMuPDF redaction plus insert. Scanned and mixed PDFs decided per page. Page order and dimensions kept.
- OpenCV FAST inpaint and LaMa AI inpaint, chosen by background complexity, with a manual override. LaMa is loaded once, checksummed, and cropped to the mask.
- Undo, redo, reset, preview, export. Frontend on port 8742, API on 8741, Vite proxies `/api`.
- Unchanged characters copied from the original line.
- Tests under `tests/`. Run `/workspace/.venv/bin/python -m pytest`. The print-style, visual-match, and font-match files were the last focused run (10 passed). Full unit count before the color work was 36, ignoring `e2e_acceptance.py`.
- Measured timings live in `docs/PERFORMANCE.md`. Do not invent new ones.

`docs/RESEARCH.md`, `docs/ARCHITECTURE.md`, `docs/adr/004-fonts-and-storage.md`, and the README still describe page-letter copy plus a 45% font gate as the solution. That description is what the owner rejected. Update those files only after a render survives the checks below.

## What to build

Replace the raster draw for changed characters. Keep the app, the API, and the “copy unchanged pixels” behavior.

1. Erase only the characters that change. Reconstruct that background with LaMa when the ring is textured, otherwise OpenCV. Do not inpaint a solid rectangle over the whole line.
2. Place the new word at its natural letter widths, scaled uniformly to the original ink height. If it is wider than the slot, tighten tracking, then uniform-scale the whole word. Never scale x and y differently. If it is narrower, leave paper in the gap. Match the line’s alignment.
3. Transfer the measured fill color and, when the boundary ring differs, the outline color and thickness. Transfer a real shadow offset. Match blur and row fade so the edge energy stays inside the existing test band.
4. Prefer letter shapes cut from the same page, at uniform scale, because a thermal face is not in the bundled set. For a letter the page does not contain, do not fall back to an unstyled Liberation draw. Render that character with a text-replacement model, or with a bundled shape only after its stroke width has been matched and it has been colored, outlined, and blurred like the line. Say in the UI when the shape is synthesized. Do not disable Apply because a letter is new.
5. For the cases the classical path cannot carry (outlined color, light-on-dark, rotation, a face with no usable samples), call a GPU or paid text-edit model on the masked line, conditioned on the new string and a crop of the original line. Reassemble so pixels outside the mask are untouched. Good candidates to evaluate, not to assume: AnyText2, TextDiffuser-2, or a paid image-edit endpoint that accepts a mask plus a style crop (OpenAI image edit, Gemini image, fal, Replicate). Pick by a visual test, not by the vendor’s claim. Keep the call behind something like `InpaintingProvider`, with the local path as fallback when no key or GPU is present. Never send the request silently. If the key is missing, say so.
6. Stop printing “Visual match NN%” as the result. The notice can say which engine ran. The history row should not treat the score as proof.

## How to decide it worked

Run these, and keep the images:

- Tesco receipt `/tmp/bills/tesco.jpg` (also `/home/ubuntu/Downloads/Tesco_grocery_receipt_Finchley_1994.jpg`), slogan “EVERY LITTLE HELPS”. A same-text rewrite should be nearly identical. A different word whose letters exist on the page should match stroke width and gray level, and the new word’s aspect ratio must match the glyphs, not the old span. Prefix pixels that did not change must stay at mean absolute difference under 4, as in `tests/test_print_style.py`.
- A replacement that includes a letter not on the page. It must still be drawn, and it must not look like a default sans dropped on the receipt.
- The yellow word with a black outline in `/tmp/color-cases/yellow_outline.jpg` (“NIGHT MARKET”). After the edit, the outline must still be a separate dark ring. Flat yellow fails.
- One saturated color, one light-on-dark, one rotated line. Green-on-stripes and the red word with a blue shadow in `/tmp/color-cases/` are the segmentation cases that still return no letter cuts.

Record stroke width, ink-median color distance, edge energy, whether an outline is present, and the ratio of each new letter’s width to its height versus the donor glyph. Do not record a match percent as the conclusion.

## Run facts

Branch `main`. Latest commit when this handoff was written: `d0e8232` (“Keep thin letters so colored lines can be rebuilt.”).

```bash
# API
REWORDS_STORAGE_DIR=/tmp/rewords-smoke3 \
REWORDS_CLEANUP_HOURS=100000 \
PADDLEX_HOME=/workspace/models/paddlex \
PADDLE_PDX_CACHE_HOME=/workspace/models/paddlex \
PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK=True \
FLAGS_use_mkldnn=0 \
/workspace/.venv/bin/uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8741

# UI
cd frontend && npm run dev -- --host 127.0.0.1 --port 8742
```

Set the Paddle variables before importing `paddleocr`. Models: `models/lama/big-lama.pt` (SHA-256 in `models/checksums.json`) and `models/paddlex/official_models/`. Weights are not in git; `python scripts/download_models.py` fetches them. This machine had no NVIDIA GPU. Torch is the CPU wheel `2.5.1`; Paddle is `3.2.0` CPU. Install those from their own indexes before `backend/requirements.txt`, or pip will pull CUDA torch.

Playwright can drive Chrome at `http://127.0.0.1:9333` (`connect_over_cdp`). Region rows are `button[data-testid^=region-]`. The file input exists only on the empty upload screen (`data-testid=file-input`). Do not click SVG nodes with `data-testid^=region-`; they are not HTMLElements.

Do not commit `.venv`, `node_modules`, `models/`, `storage/`, `frontend/dist`, or the Paddle cache. Do not open a pull request. Commit and push to `main`.

## File map

| Path | Role |
| --- | --- |
| `backend/app/rendering/print_style.py` | Copy unchanged pixels. Stretch and flat recolor live here. |
| `backend/app/rendering/glyph_bank.py` | Cut and replay page letters. |
| `backend/app/image/editing.py` | Raster replace. Whole-string glyph gate and font refusal. |
| `backend/app/rendering/visual_match.py` | Measure and score. Not a proof of an unedited look. |
| `backend/app/rendering/font_match.py` | Bundled-face IoU. `MIN_FONT_MATCH = 0.45`, `SOFT_FONT_MATCH = 0.34`. |
| `backend/app/image/style.py` | Color and the font-match call. |
| `backend/app/image/masking.py` | Text mask and FAST vs AI complexity. |
| `frontend/src/App.tsx` | Apply block and the “Visual match” notice. |
| `tests/test_print_style.py` | Prefix pixels, edge energy, ink gray. Do not loosen. |
| `tests/test_visual_match.py` | `test_missing_letters_and_a_weak_font_are_not_drawn` expects `FONT_MATCH_LOW` for “QUIZ NIGHT”. Update it when missing letters are supposed to render. |
| `tests/test_font_match.py` | Blank image with confidence 0.27 must still refuse. There is no ink to copy. |
