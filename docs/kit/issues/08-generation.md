Title: Generate on the mock provider and download

Labels: replate, mvp

Spec: specs/SPEC-generation.md

## Why

This is the product loop with a zero cloud bill. After it merges, stop.

## Acceptance

- `POST /api/generations` follows the eight steps in the spec, including 402, 429, and 409.
- Failure inserts `failed` and does not change the ledger.
- Success stores the PNG, then debits 10 in the same transaction as the succeeded row.
- Button copy, best-effort line, `Replacing…`, and `Download PNG` match `DESIGN.md`.
- Playwright: upload, fixture line, type `HELLO`, download, bytes differ, balance goes from 10 to 0, reload keeps 0.
- `Recent` lists the generation.

## Verify

```
pnpm test lib/generation/run.test.ts
pnpm exec playwright test e2e/replace.spec.ts
pnpm dev
```

Leave `pnpm dev` running only long enough to confirm `http://localhost:3000` answers, then report that URL in the pull request.

## Files

`lib/generation/run.ts`, `lib/generation/run.test.ts`, `app/api/generations/route.ts`, `app/api/generations/[id]/file/route.ts`, `components/GenerateBar.tsx`, `e2e/replace.spec.ts`

## Out of this issue

Live providers. This pull request must pass with no API keys. Stop here even if the user said `continue through 15`.
