# Performance

Numbers below are from `python scripts/benchmark.py` on this CPU-only machine (4 cores, no NVIDIA GPU). They are wall times for one generated fixture, including JSON overhead, not a statistical benchmark. Re-run the script after hardware or model changes. `docs/perf-results.json` is gitignored; paste a fresh run over the table if you measure again.

Measured on 3 October 2026 with `python scripts/benchmark.py` (CPU wheel, 4 cores, no NVIDIA device). `nvidia-smi` is not installed. Both `torch_device()` and `paddle_device()` reported `cpu`, so GPU utilization is 0. A later sample of the API process during the browser acceptance run (2-second windows over 60 seconds) peaked at 328% CPU, about 3.3 of the 4 cores, and averaged 105% including idle time between requests. Paddle's own threads use more than the single Python inference lane.

| Step | Measured |
| --- | --- |
| PaddleOCR model load (first detect in the process) | 5703 ms, device cpu |
| First image detect, including that load (1 region) | 8067 ms wall, 8009 ms inside detect |
| Warm image OCR predict (model already loaded) | 1369 ms |
| Second detect of the same image | 1408 ms wall |
| OpenCV inpaint only (11,786 mask pixels, radius 5) | 26 ms |
| Fast replace, one line, flat background (mask + draw + save) | 263 ms wall, complexity 0.01 |
| LaMa model load | 453 ms, RSS 1279 MB at load, device cpu |
| LaMa inpaint on a 460×160 crop | 943 ms |
| AI replace, textured line, including the LaMa load | 1526 ms wall, mode `ai`, no fallback |
| 3-page native PDF detect (text layer, no OCR) | 17 ms wall, 8 ms inside detect |
| Native PDF text replace | 30 ms wall |
| 3-page scanned PDF detect | 18068 ms wall (OCR predicts 5715, 5944, and 5656 ms) |
| Process RSS | 117 MB before models, 1840 MB after Paddle + LaMa + the scanned PDF |

Image processing other than inpainting is inside the fast replace figure: mask building, color estimation, and text drawing account for most of the 263 ms once the 26 ms OpenCV call is subtracted. Native PDF work does not rasterize the page. A scanned edit would add one inpaint of that page; the benchmark stops at detect for the scan.

What was optimized only after it showed up in the design of the pipeline, not from a micro-benchmark sweep:

- OCR and LaMa stay loaded.
- Both run on one Python inference thread so they do not compete, and so Paddle is not called from a random request thread (that produced intermittent OCR failures). Native libraries still fan out across cores; the acceptance sample peaked at 328% CPU.
- LaMa runs on a crop around the mask with a 48 px margin, not the full page.
- Page previews and thumbnails are cached by page version. An edit drops the cache for that page only.
- Native PDF edits do not rerender other pages into the exported file. Scanned exports replace only the edited page.
- A second `detect-text` call still re-runs OCR today. The normalized regions are stored on the document, and the UI does not call detect twice. The benchmark's "cached" figure is a second full detect, so it shows model-load cost disappearing, not a skipped OCR.

GPU: `torch.cuda` and Paddle's CUDA device count are checked at runtime. This machine has no GPU, so every number is CPU.
