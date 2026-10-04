# Security review

This is a single-user local tool. There is no authentication. The threats that matter are malicious files, path traversal, and unsafe model loading.

## What is enforced

- Type comes from magic bytes (`PNG`, `JPEG`, `%PDF`). The filename extension is not trusted.
- Uploads stop at `REWORDS_MAX_UPLOAD_BYTES` (default 25 MB) while they are still being read.
- Pillow's pixel cap is set to 40 million so a small compressed image cannot expand without bound. PDF pages are also capped (`REWORDS_MAX_PAGE_PIXELS`, and a long-side cap when rendering).
- PDF encryption without an empty password is rejected. Corrupt PDFs return `CORRUPTED_PDF` instead of a stack trace to the user (the traceback is logged).
- Stored names are `original.pdf` / `original.jpg` / `original.png` inside a 32-hex directory. The display name is the basename, with characters outside a small set replaced, and `..` cannot be part of the storage path.
- `LocalStorage.path` resolves the target and requires it to stay under that document directory.
- Each document has its own directory. Startup deletes document directories older than `REWORDS_CLEANUP_HOURS` (default 24).
- Document state is JSON, not pickle.
- LaMa weights load only from `models/lama/big-lama.pt` after the SHA-256 in `models/checksums.json` matches. A mismatch refuses the load and the edit falls back to OpenCV.
- User input is not passed to a shell. The app does not call `subprocess` with filenames.
- Replacement text is limited to 400 characters and cannot be blank.
- Unexpected exceptions are logged with a traceback and returned as `INTERNAL` with a fixed message. OCR, export, and render failures do not echo the exception string (which can contain filesystem paths) back to the client.

## Model loading

`torch.jit.load` is not pickle, but a TorchScript archive can still contain operators. The checksum makes sure we load the file we pinned, not a substituted path from the request. It does not make TorchScript a data-only format. The README says so.

Paddle caches under `models/paddlex/` because `PADDLE_PDX_CACHE_HOME` is set before import. Those files come from the Paddle model host on first run.

## Residual risk

- Anyone who can reach the port can upload files and fill the disk up to the size and page limits. Bind to `127.0.0.1`, which the README does.
- A hostile PDF can still stress PyMuPDF. The page and byte caps reduce that; they are not a full sandbox.
- Cleanup uses directory mtime. A document that is edited keeps a fresh mtime and is not deleted out from under the user during the same day.
