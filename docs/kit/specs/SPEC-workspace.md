# Spec: workspace

Module id: `workspace`. Depends on `shell`, `storage`.

## Objective

The user drops one image, sees it, and can select lines or draw a box. This module does not call a model.

## Commands

```
pnpm test lib/images/accept.test.ts
pnpm exec playwright test e2e/upload.spec.ts
```

## Project structure

```
app/api/images/route.ts                 POST multipart
app/api/images/[id]/file/route.ts       GET png for the owner
lib/images/accept.ts                    size, magic bytes, sharp, bomb check
components/ImageStage.tsx               preview, boxes, draw tool
components/LineList.tsx                 text, replacement field, checkbox
```

## Behavior

`POST /api/images` accepts one file field named `file`.

Accept only:

- PNG bytes starting `89 50 4E 47`
- JPEG bytes starting `FF D8 FF`
- WebP bytes `RIFF` and `WEBP` at offset 8

Reject anything else, including GIF and SVG, with HTTP 415 and the sentence “Use a PNG, JPG, or WebP.”

Reject over 8 MB with HTTP 413 before decode.

Decode with sharp. Strip EXIF by re-encoding to PNG. If the long edge is above 8192, or the pixel count is above 16 million, reject with HTTP 400. If the long edge is above 2048, resize so the long edge is 2048, without enlarging.

Store that PNG. Insert `images`. Return `{ id, width, height }`.

`GET /api/images/:id/file` returns the PNG only when `user_id` is the current user. Anyone else gets 404, not 403.

Until auth exists, the current user is the bootstrap user in `SPEC-auth.md`.

The stage maps pointer positions to image pixels, not CSS pixels. A drawn box is `{ x, y, width, height }` in those pixels, integers, width and height at least 8. Drawing adds a row the user can type into. Empty replacement means remove.

Selected box: 2px `--green`. Hovered box: 1px `--ink`. Selected row uses `--wash` and a checkbox, not color alone.

## Code style

Validate the multipart file before sharp. Zod parses the JSON response the client reads. The client sends no URL. There is no “import from link” field.

## Testing strategy

- Unit: a text file renamed `.png` is rejected. A real PNG is accepted and the stored file has no EXIF orientation tag.
- Unit: an 8000px edge is rejected.
- Playwright: drop a generated PNG, see an `<img>`, no console error.

## Boundaries

- Always: re-encode. Check ownership.
- Ask first: raising the 8 MB cap.
- Never: `fetch` a user-supplied URL. Never trust the client’s MIME type alone.

## Success criteria

- Bad bytes never hit the database.
- A JPEG preview is the re-encoded PNG.
- Draw a box and it survives in React state in image pixels.

## Open questions

None.
