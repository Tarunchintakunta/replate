Title: Implement the Gemini editor

Labels: replate, mvp

Spec: specs/SPEC-editor.md

## Why

The first real edit should use an API key the builder can create today. The chat subscription is not that key.

## Acceptance

- Read the current Google image-edit docs. Put the doc URL in the pull request body.
- `GeminiEditor.edit` sends the 1024-long-edge PNG and the prompt, with a 60s timeout.
- Default model `gemini-2.5-flash-image` from `GEMINI_IMAGE_MODEL`.
- Unit test uses a mocked response and a tiny PNG. No network.
- Missing `GEMINI_API_KEY` throws a clear error and does not fall back to mock.
- `scripts/smoke-live.ts` exists and is not called from `pnpm test`.
- Do not run the live script unless the user asks in that session. One run maximum.

## Verify

```
pnpm test lib/editor/gemini.test.ts
```

## Files

`lib/editor/gemini.ts`, `lib/editor/gemini.test.ts`, `scripts/smoke-live.ts`

## Out of this issue

A UI redesign. The provider pill may read `Gemini` when `GET /api/health` says the provider is gemini and the key is present as a boolean. The health route must not return the key.
