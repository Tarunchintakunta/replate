Title: Add the editor interface and the mock

Labels: replate, mvp

Spec: specs/SPEC-editor.md

## Why

CI and the desk must prove a changed PNG before any paid API exists.

## Acceptance

- Types match `ARCHITECTURE.md`. `getEditor()` supports `mock`, `gemini`, and `wavespeed`, and throws on anything else.
- `mock` returns a different valid PNG for a normal replacement and for an empty `to`.
- Gemini and WaveSpeed classes may be stubs that throw `Not implemented` until issues 09 and 10. `getEditor()` still returns them so the switch exists. They must already `import "server-only"`.
- Prompt builder is covered by a unit test for one replacement and one empty `to`.
- No network in the test.

## Verify

```
pnpm test lib/editor/mock.test.ts lib/editor/prompt.test.ts
```

## Files

`lib/editor/types.ts`, `lib/editor/index.ts`, `lib/editor/prompt.ts`, `lib/editor/prompt.test.ts`, `lib/editor/mock.ts`, `lib/editor/mock.test.ts`, `lib/editor/gemini.ts`, `lib/editor/wavespeed.ts`

## Out of this issue

The HTTP generation route. Wiring the button is issue 08.
