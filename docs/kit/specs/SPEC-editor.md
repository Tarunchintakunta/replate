# Spec: editor

Module id: `editor`. Depends on `storage`.

## Objective

One interface edits the image. v1 has three implementations: `mock`, `gemini`, `wavespeed`. The route calls `getEditor()`. It does not know which HTTP API is behind it.

## Commands

```
pnpm test lib/editor/mock.test.ts
pnpm test lib/editor/gemini.test.ts
pnpm test lib/editor/wavespeed.test.ts
```

Gemini and WaveSpeed unit tests mock `fetch`. They do not use network.

## Project structure

```
lib/editor/types.ts
lib/editor/index.ts          getEditor()
lib/editor/prompt.ts         the text in ARCHITECTURE.md
lib/editor/mock.ts
lib/editor/gemini.ts
lib/editor/wavespeed.ts
```

The TypeScript types are exactly the block in `ARCHITECTURE.md`. Do not add a fourth provider in v1.

## Behavior

`getEditor()` reads `EDITOR_PROVIDER`. Default `mock`. `gemini` without `GEMINI_API_KEY` throws at the call with a clear error, not a silent fallback. Same for WaveSpeed. An unknown provider throws at startup.

Timeout on every outbound request: 60 seconds. A timeout throws. The caller writes a failed generation and does not touch the ledger.

Before the call, resize a copy so the long edge is 1024. Do not upscale. The stored original stays at its stored size. The returned PNG is what the user downloads.

Prompt text is the template in `ARCHITECTURE.md`. Empty `to` means remove the text and reconstruct the background. The prompt is built on the server. It is not a client prop.

### mock

No network. Draw a flat rectangle over each box and set the replacement string in dark ink, or the word `removed` is not drawn when `to` is empty: the box becomes a flat sample of the pixel just outside its top-left corner. Output must be a valid PNG whose bytes differ from the input when there is at least one replacement. `provider` is `mock`, `model` is `mock`.

### gemini

Read the current Google AI image-edit docs on the day you implement this, and cite the doc URL in the pull request. Start from `GEMINI_IMAGE_MODEL`, default `gemini-2.5-flash-image`. Send the PNG and the prompt. Parse the returned image bytes. If the model id 404s, stop. Do not guess a chain of model names.

The unit test feeds a fake response that contains a tiny base64 PNG and asserts `edit()` returns those bytes and `provider: "gemini"`.

### wavespeed

Read the current WaveSpeed docs for `wavespeed-ai/flux-kontext-pro` on the day you implement this. Default model env `WAVESPEED_EDIT_MODEL`. One request per generation, not a second eraser call. The unit test uses a fake HTTP response the same way as Gemini.

`scripts/smoke-live.ts` calls the selected live provider once against a local fixture. It is not part of `pnpm test` and not part of CI. Run it only when the user asks, and at most once to confirm the key.

## Code style

```ts
export function getEditor(): ImageEditor {
  const name = process.env.EDITOR_PROVIDER ?? "mock"
  if (name === "mock") return new MockEditor()
  if (name === "gemini") return new GeminiEditor()
  if (name === "wavespeed") return new WaveSpeedEditor()
  throw new Error(`Unknown EDITOR_PROVIDER: ${name}`)
}
```

No SDK unless the official docs require one. `fetch` is enough. Do not add the Fal SDK or the Replicate SDK.

## Testing strategy

Mock test: input PNG in, different valid PNG out, including the empty-`to` case. Gemini and WaveSpeed tests: no socket. A test that the client bundle does not import `lib/editor/gemini.ts` belongs to `SPEC-proof.md`.

## Boundaries

- Always: server-only modules. `import "server-only"` at the top of gemini.ts and wavespeed.ts.
- Ask first: a new provider, a retry loop, or a second model call per click.
- Never: call the provider from a React component. Never put the API key in a `NEXT_PUBLIC_` variable. Never run a local FLUX weight.

## Success criteria

- `EDITOR_PROVIDER=mock` completes with zero keys.
- Gemini and WaveSpeed tests pass offline.
- Unknown provider fails fast.

## Open questions

None. The vendor HTTP shape is looked up at implementation time, not invented here.
