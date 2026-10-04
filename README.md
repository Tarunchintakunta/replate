# Local ReWords

Replace text inside a PNG, JPEG, or PDF on your own machine. Text is detected, the original strokes are removed (inpainting or PDF redaction, not a box drawn on top), and new text is drawn to match the size, color, weight, and alignment as closely as the bundled fonts allow. Nothing in the core path calls a paid API.

The original upload is never modified. Edits are stored beside it, with undo, redo, and reset.

## Prerequisites

| Tool | Used here | Notes |
| --- | --- | --- |
| Python | 3.12 | 3.12.3 is the version this repo was installed and tested with. Create the venv with that interpreter. |
| pip | current | `python -m pip install -U pip` |
| Node.js | 20 or newer | Verified with Node 22. `npm` comes with Node. |
| npm | 10 | `npm install` inside `frontend/`. pnpm is not required. |
| GPU | none required | CPU wheels are the tested path. An NVIDIA GPU is used only if PyTorch reports CUDA or the installed Paddle build was compiled with CUDA and sees a device. Do not install GPU wheels unless the driver matches; a mismatch breaks startup. |

Disk: the PaddleOCR models are a few hundred MB under `models/paddlex/`. LaMa is about 196 MB at `models/lama/big-lama.pt`. The CPU PyTorch wheel is larger than that. A 4-core machine with 8 GB of free RAM is enough; this project was exercised on CPU with no NVIDIA device.

## Backend (macOS and Linux)

From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install -r backend/requirements.txt
```

`paddleocr==3.3.2` is pinned in `backend/requirements.txt` and expects that Paddle 3.2 CPU wheel. Install the wheel first so pip does not try to replace it.

## Backend (Windows)

From the repository root, in PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu
pip install paddlepaddle==3.2.0 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/
pip install -r backend\requirements.txt
```

If `py -3.12` is not recognized, install Python 3.12 from python.org and try again. If activation is blocked, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or call `.venv\Scripts\activate.bat` from Command Prompt.

## Model files

Weights are not in git. From the repository root, with the venv active:

```bash
python scripts/download_models.py
```

Windows:

```powershell
python scripts\download_models.py
```

The script writes:

| Path | What it is |
| --- | --- |
| `models/lama/big-lama.pt` | LaMa TorchScript checkpoint. SHA-256 must match `models/checksums.json`. |
| `models/paddlex/official_models/` | PaddleOCR detection, English recognition, and text-line orientation models. Created on first use. The script runs one OCR so the download happens here instead of on the first click. |

`models/checksums.json` is already in the repo. Do not point LaMa at a different file unless you update that checksum. A mismatch is refused and edits fall back to fast inpainting.

Fonts are already in `fonts/` (Liberation Sans, Serif, Mono, regular and bold) with `fonts/LICENSE` (SIL Open Font License). You do not download those.

## Run the backend

macOS and Linux, from the repository root, venv active:

```bash
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8741
```

Windows, from the repository root:

```powershell
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8741
```

Leave this terminal open. `GET http://127.0.0.1:8741/api/health` should return `"status": "ok"`. `inpaint_ai.ready` is true after the LaMa file and checksum are in place. OCR loads on the first detect, not at startup.

## Run the frontend

A second terminal, from the repository root:

```bash
cd frontend
npm install
npm run dev
```

Windows is the same. The dev server listens on `http://127.0.0.1:8742` and proxies `/api` to port 8741.

## Open the app and try a replacement

1. Open [http://127.0.0.1:8742](http://127.0.0.1:8742).
2. Drop a PNG, JPG, or PDF, or choose a file. You can generate samples with `python scripts/generate_samples.py` (files land in `tests/fixtures/generated/`).
3. Wait until regions appear. The first document also loads PaddleOCR, which is the slow part.
4. Click a highlighted line, or the same line in the list on the right.
5. Type the replacement and press **Apply change**. The banner names the mode: fast OpenCV, LaMa, or a PDF text edit. Auto uses LaMa only when the background around the words looks textured.
6. Use **Undo**, **Redo**, and **Reset**. **Before / after** compares the original page with the edit.
7. **Export JPG** or **Export PNG** for an image. **Export PDF** for a PDF. The download is the edited file. The upload itself is still in `storage/<id>/original.*`.

For a PDF, thumbnails along the top switch pages. A text page is edited in the PDF. A scanned page is edited as an image. A file can contain both.

## Tests

With the venv active, from the repository root:

```bash
python -m pytest
```

Windows: `python -m pytest`

That runs the backend suite (images, colors, texture, rotation, native PDFs, scanned PDFs, mixed PDFs, undo/redo, export, and error cases). The first run is slower because Paddle loads once.

Frontend typecheck and production build:

```bash
cd frontend
npm run build
```

Optional browser acceptance (backend on 8741 and `npm run dev` on 8742 already running):

```bash
pip install playwright==1.49.1
python -m playwright install chromium
python tests/e2e_acceptance.py
```

## Configuration

Environment variables use the prefix `REWORDS_`. Defaults are fine for local use.

| Variable | Default | Meaning |
| --- | --- | --- |
| `REWORDS_STORAGE_DIR` | `storage/` | Where uploads and edits go |
| `REWORDS_MODELS_DIR` | `models/` | LaMa file and Paddle cache root |
| `REWORDS_FONTS_DIR` | `fonts/` | Bundled faces |
| `REWORDS_MAX_UPLOAD_BYTES` | 26214400 | 25 MB |
| `REWORDS_MAX_PDF_PAGES` | 30 | Page cap |
| `REWORDS_RENDER_DPI` | 144 | Preview and scan render scale, before the long-side cap |
| `REWORDS_OCR_LANG` | `en` | Paddle language code |
| `REWORDS_CLEANUP_HOURS` | 24 | Delete document folders older than this on startup |
| `REWORDS_CORS_ORIGINS` | localhost and 127.0.0.1 on port 8742 | Browser origins |

The process also sets `PADDLE_PDX_CACHE_HOME` and `PADDLEX_HOME` to `models/paddlex`, turns off the PaddleX model-host connectivity check, and disables oneDNN (`FLAGS_use_mkldnn=0`), which has hung or crashed some CPU wheels.

## Troubleshooting

- **Health check says LaMa is not ready.** Run `python scripts/download_models.py`. If you copied the file by hand, the SHA-256 must match `models/checksums.json` or the loader will refuse it.
- **First detect sits for a long time.** Paddle is downloading into `models/paddlex/official_models/`. The download script does this up front. Later detects only pay for inference.
- **`OCR_FAILURE` immediately.** Confirm `paddlepaddle==3.2.0` and `paddleocr==3.3.2` in `pip show`, and that the venv is the interpreter running uvicorn.
- **Paddle prints a connectivity check.** Restart from a process that imported the app after `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK` was set. The README commands do that inside the app. The public log line mentions a shorter variable name; the code reads `PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK`.
- **Port already in use.** Stop the other process or change 8741 and the proxy in `frontend/vite.config.ts` together.
- **Windows cannot activate the venv.** Use Command Prompt and `.venv\Scripts\activate.bat`.
- **No text found.** The page may be blank, decorative, or too small. The API returns `NO_TEXT_DETECTED` and the page stays on screen.
- **AI button still says fast.** The banner includes the fallback reason. Missing weights, a bad checksum, or a Torch load error all do this on purpose.

## Known limitations

- The original font file is not recovered. Letters that stay in the string are copied from the original line. New letters are taken from elsewhere on the page and repainted to match that line's ink and blur. A bundled face is used only for a letter the page does not contain, and only when that match is at least 45%. A weak face is refused. Italic PDF spans use the regular face of the same family. Different letters cannot be the same pixels. The check is a measured score, not a claim that the typeface was identified.
- A much longer replacement can crowd the next word. Native PDF text shrinks to the gap on that line. Image text may extend past the old box, up to about 1.45 times the width, then shrinks.
- Default OCR is English, and the fonts are Latin. Devanagari and other scripts will not render correctly with this font set even if you change `REWORDS_OCR_LANG`.
- LaMa helps on texture and is slow on CPU. Very large solid masks are a weak case for this checkpoint; text-sized holes are what it is used for. Flat paper stays on OpenCV in Auto.
- Rotated image text follows the detected quad. Native PDF rotation uses a text matrix when the span direction is not horizontal; curved text is not reconstructed.
- A scanned page that is edited is re-encoded as an image in the exported PDF. Other pages are not.
- A second OCR of a very noisy edit can misread a glyph even when the old word is gone.
- There is no login. Bind the servers to localhost.
- `torch.jit.load` checks a pinned checksum and still is not a data-only format. See `docs/SECURITY.md`.
- GPU support is implemented and was not run here, because this machine has no NVIDIA GPU.

## Architecture

See `docs/ARCHITECTURE.md`. Short version: the UI calls FastAPI. Images and scans go through a mask, then OpenCV or LaMa, then Pillow. Real PDF text is redacted and reinserted with PyMuPDF. `OCRProvider`, `InpaintingProvider`, `PDFProcessor`, `TextRenderer`, and `StorageProvider` are the seams for a later engine, S3, or database. Product scope is in `docs/PRODUCT.md`. Choices are in `docs/RESEARCH.md` and `docs/adr/`.

## Future

Local translation, script-specific fonts and OCR models, a stronger italic/weight estimate, and optional cloud providers behind the same interfaces. Not in this prototype.
