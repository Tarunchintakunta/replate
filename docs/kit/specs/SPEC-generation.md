# Spec: generation

Module id: `generation`. Depends on `workspace`, `ocr`, `editor`, `credits`.

## Objective

One click replaces every selected line, stores the PNG, then spends 10 credits. A failure spends nothing. The user downloads the PNG.

## Commands

```
pnpm test lib/generation/run.test.ts
pnpm exec playwright test e2e/replace.spec.ts
```

Playwright uses `EDITOR_PROVIDER=mock` and `OCR_MODE=fixture`.

## Project structure

```
lib/generation/run.ts
lib/generation/run.test.ts
app/api/generations/route.ts
app/api/generations/[id]/file/route.ts
components/GenerateBar.tsx
```

## Behavior

`POST /api/generations` body, Zod:

```ts
const Body = z.object({
  imageId: z.string().uuid(),
  lines: z.array(z.object({
    lineId: z.string().uuid().nullable(),
    from: z.string().max(200),
    to: z.string().max(200),
    box: z.object({
      x: z.number().int().nonnegative(),
      y: z.number().int().nonnegative(),
      width: z.number().int().positive(),
      height: z.number().int().positive(),
    }),
  })).min(1).max(20),
})
```

Server steps, in order:

1. Resolve the current user. 401 if none.
2. Load the image. 404 if it is not theirs.
3. Count generations for this user in the last hour. If 10 or more, return 429 and do not call the editor.
4. If balance is under 10, return 402 and do not call the editor.
5. Call `editor.edit`. On throw, or on a body that is not a PNG, insert `generations.status = failed` and the error string, commit, return 502. Ledger untouched.
6. Write `storage/generations/{id}.png`.
7. In one transaction: insert generation `succeeded` with `output_key`, insert `generation_replacements`, `debitGeneration`.
8. If the transaction throws, delete the PNG you just wrote and return 500. Ledger untouched.

The button label is `Replace text` and the cost line is `10 credits`. While the request runs, the label is `Replacing…` and the button is disabled. The image stays on screen.

Near the button, always: `Font and background matching is best-effort.`

Success swaps the preview to the new PNG and shows a text button `Download PNG`. No modal.

`GET /api/generations/:id/file` streams the PNG for the owner only.

`GET /api/generations?limit=20` returns the latest rows for the owner: id, status, created_at. The UI lists them under the lines as `Recent`. Clicking a succeeded row loads that file into the preview.

A second request while one is in flight for the same user returns 409.

## Testing strategy

Unit, with the mock editor and a temp database:

- Happy path moves balance from 10 to 0 and the output file exists.
- Editor throw leaves balance at 10 and status `failed`.
- Balance 0 never calls `edit`. Assert with a spy.
- 11th attempt within the hour returns 429 without `edit`.

Playwright:

- Fixture OCR line `SALE`, type `HELLO`, generate, download, file bytes differ from the upload, balance shows 0.
- Reload and the balance is still 0.

## Boundaries

- Always: charge after the file hits disk, inside the transaction described above.
- Ask first: retries against the live provider. Mock has no retry either.
- Never: charge on failure. Never let the browser talk to Gemini or WaveSpeed.

## Success criteria

Playwright happy path passes with no API key. The failure unit test passes. This is the checkpoint. Stop and give the user `http://localhost:3000`.

## Open questions

None.
