Title: Prove a failed generation does not charge

Labels: replate, mvp

Spec: specs/SPEC-generation.md, specs/SPEC-credits.md

## Why

The success path can hide a debit that runs too early. This slice locks the failure path from the UI.

## Acceptance

- A test double whose `edit()` throws is selectable in tests without a new env provider. Keep production providers as they are. The double lives in the test file.
- After the throw, balance is unchanged, a `failed` row exists, and the PNG was not written.
- Playwright can force the failure with `EDITOR_PROVIDER=mock` plus a test-only header `x-replate-fail: 1` that the server honors only when `NODE_ENV` is `test`. The page shows one danger sentence and the balance stays 10.
- The generate button is disabled at balance 0, label `No credits left.`
- A request at balance 0 does not call `edit`.

## Verify

```
pnpm test lib/generation/run.test.ts
pnpm exec playwright test e2e/failure.spec.ts
```

## Files

`lib/generation/run.ts`, `e2e/failure.spec.ts`, the generate button component

## Out of this issue

New providers. Do not treat this header as a feature. It must not work in `pnpm dev` when `NODE_ENV` is `development`.
