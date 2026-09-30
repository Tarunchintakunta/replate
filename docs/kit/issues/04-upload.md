Title: Accept an upload and preview it

Labels: replate, mvp

Spec: specs/SPEC-workspace.md

## Why

Nothing else matters until a real PNG is on the desk and a fake PNG is refused.

## Acceptance

- `POST /api/images` enforces 8 MB, magic bytes, sharp re-encode, EXIF strip, and the bomb limits in the spec.
- JPEG and WebP become stored PNGs. GIF and SVG return 415 and the sentence `Use a PNG, JPG, or WebP.`
- The preview `<img>` loads `GET /api/images/:id/file`.
- The current user is the bootstrap user `local@replate.test` from `SPEC-auth.md`, created with one trial row.
- A file owned by a different user id returns 404.
- Draw tool writes a box in image pixels. No model call.

## Verify

```
pnpm test lib/images/accept.test.ts
pnpm exec playwright test e2e/upload.spec.ts
```

## Files

`lib/images/accept.ts`, `lib/images/accept.test.ts`, `app/api/images/route.ts`, `app/api/images/[id]/file/route.ts`, `components/ImageStage.tsx`, `e2e/upload.spec.ts`

## Out of this issue

OCR and generation.
