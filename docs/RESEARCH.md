# Research notes

Compared for a local CPU prototype. Accuracy comments are from published behavior and from running the chosen stack on generated fixtures in this repo, not from a public leaderboard.

## OCR and text detection

| Option | Local | CPU | Notes |
| --- | --- | --- | --- |
| PaddleOCR 3.3 / PP-OCRv5 | Yes | Yes | Strong on clean print. Returns quads, text, and scores. Heavy install. Apache-2.0. |
| Tesseract | Yes | Yes | Easier install, weaker on rotated and scene text. |
| EasyOCR | Yes | Yes | Good, but another Torch model competing with LaMa for RAM. |
| Cloud Vision / Textract | No | n/a | Paid, and the file leaves the machine. |

Decision: PaddleOCR behind `OCRProvider`. Verified: `paddleocr==3.3.2` with `paddlepaddle==3.2.0` (CPU wheel) on Python 3.12 reads "Welcome to Paris" from a generated JPEG. The UI consumes normalized regions only.

A separate text-segmentation network was not added. Paddle already returns a quad. Inside that quad, a color-distance mask finds the strokes. A second model would mostly repeat the detector and add another download.

## Inpainting

| Option | When it is enough | Cost |
| --- | --- | --- |
| Solid fill | Flat color only | Instant, leaves a box on texture |
| OpenCV TELEA | Flat and lightly noisy paper | Milliseconds, local, no weights |
| LaMa (TorchScript) | Textured or photographic backgrounds | ~200 MB weights, Torch, about a second or more on CPU for a text crop |
| Diffusion inpainting | Large invented backgrounds | Too heavy for this CPU prototype |

AI is needed when the surrounding pixels are not a flat color. Auto mode measures the ring around the mask (standard deviation and edge density). Below 0.42 it stays on OpenCV. At or above 0.42 it uses LaMa, and falls back to OpenCV if the weights are missing or fail to load. The response records which mode ran.

Deterministic CV is the default because most documents are paper. Generative fill is reserved for texture.

## Fonts

Exact font identification is not claimed. Characters that stay the same are copied from the original line, so those pixels do not change. Characters that change are built from other letters on the page, then repainted with that line's ink color, blur, and row fade. A generative text editor was not used: SRNet, MOSTEL, and similar models need a GPU and a trained checkpoint, and they invent a face instead of keeping this page's pixels. This app runs on CPU.

If a replacement needs a letter that is not on the page, the line is drawn in the bundled face whose ink, at its natural width, overlaps the original strokes. Liberation Sans, Serif, and Mono, Barlow Condensed, and Share Tech Mono are SIL OFL. The redraw is kept only when that overlap is at least 45%. Italic PDF spans use the regular face of the same family.

## Visual match loop

After the old strokes are removed, the new line is rendered and compared with the original region. The comparison is statistical, because the words are often different: ink height, stroke width, color, letter spacing, word spacing, line spacing when the replacement has more than one line, alignment and position, rotation of the detected quad, contrast, and a drop shadow or colored outline when one is actually present. Antialiased edges are not treated as a shadow.

The loop then changes the parameter that missed (scale, tracking, weight, color, position, opacity, shadow, or outline) and renders again. It stops when the weighted score reaches 0.84 and every part is at least 0.68, or after five passes, or when a pass no longer improves the score. A page-letter copy that still misses that bar is not kept when the bundled face is also a weak match.

## PDF

| Option | Fit |
| --- | --- |
| PyMuPDF | Read spans, redact text without deleting images or line art, insert a font, render a page when a preview is needed. |
| pypdf | Weak at drawing replacement text. |
| Rasterize every page | Simple, and it destroys vector text the user did not edit. Rejected as the default. |

Native pages stay vector. A page is scanned when it has almost no text or a single image covers about 82% of the page (a full-bleed scan, including a searchable scan whose visible glyphs live in the image). Mixed files are classified per page.

## Rendering and layout

Replacement text is drawn with Pillow (antialiased) and warped into the detected quad so rotation is kept. Width grows with the new string up to about 1.45 times the original, then the size shrinks. Native PDF text is inserted on the original baseline and shrinks if it would collide with the next span on that line. This preserves a simple layout. It does not reflow paragraphs.

## Multilingual text

The default Paddle model is English (`REWORDS_OCR_LANG=en`). PP-OCRv5's English recognizer handles Latin text. Devanagari and other scripts are not covered by the bundled fonts, so unsupported glyphs cannot be drawn faithfully. Changing the language code only helps if that Paddle model is installed and a font for the script is added later.

## Reconstruction

Images: inpaint the mask, then composite the new glyphs. PDFs: either edit the text operators or, for a scanned page, replace that page with the edited render at the original page size. Page order and page boxes are copied from the source.
