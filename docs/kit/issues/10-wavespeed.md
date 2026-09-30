Title: Implement the WaveSpeed editor

Labels: replate, mvp

Spec: specs/SPEC-editor.md

## Why

FLUX Kontext Pro is the quality provider, about $0.04 a run. It stays behind the same interface.

## Acceptance

- Read the current WaveSpeed docs for `wavespeed-ai/flux-kontext-pro`. Put the doc URL in the pull request.
- One HTTP call per `edit()`. No second eraser model.
- Model from `WAVESPEED_EDIT_MODEL`, default `wavespeed-ai/flux-kontext-pro`.
- 60s timeout. Missing key throws. Mocked unit test, no network.
- Health pill can say `WaveSpeed`. It still returns only a boolean for the key.

## Verify

```
pnpm test lib/editor/wavespeed.test.ts
```

## Files

`lib/editor/wavespeed.ts`, `lib/editor/wavespeed.test.ts`, health route if the pill needs the new name

## Out of this issue

Fal, Replicate, Bria, and any local weight. Do not spend a live call unless the user asks. One call maximum.
