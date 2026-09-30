# Spec: proof

Module id: `proof`. Depends on `generation`. CI and the secret scan land after the loop works. Issue 01 may commit a lint-and-unit workflow only. Issue 14 completes it. Issue 15 adds the scan.

## Objective

`main` is green without API keys. A client bundle that contains a secret fails the build.

## Commands

```
pnpm lint
pnpm test
pnpm exec playwright test
pnpm build
pnpm exec tsx scripts/secret-scan.ts
```

## Project structure

```
.github/workflows/ci.yml
scripts/secret-scan.ts
e2e/*.spec.ts
```

## Behavior

GitHub Actions on pull requests, `ubuntu-latest`, pnpm, Node 22:

1. `pnpm lint`
2. `pnpm test` with `EDITOR_PROVIDER=mock` and `OCR_MODE=fixture`
3. `pnpm exec playwright test` with the same env
4. `pnpm build`
5. `pnpm exec tsx scripts/secret-scan.ts`

A separate job `ocr` installs `services/ocr/.venv` and runs `RUN_OCR=1 pnpm test lib/ocr/sidecar.test.ts`. No repository secrets. Cache pnpm and pip.

`secret-scan.ts` walks `.next/static` and the client chunks. It exits 1 if any file contains:

- `GEMINI_API_KEY=`
- `WAVESPEED_API_KEY=`
- `sk_live_`
- `sk_test_`
- `whsec_`
- `BEGIN PRIVATE KEY`
- the value of `AUTH_SECRET` when that value is longer than 8 characters

It also fails if `lib/editor/gemini.ts` or `lib/editor/wavespeed.ts` is imported from a file that does not start with the server-only guard and is pulled into a client component. Practical check: those two files are not referenced from any file with `"use client"`.

`scripts/smoke-live.ts` is excluded from CI.

## Testing strategy

Add a fixture client file in the secret-scan unit test, written to a temp dir, containing `sk_test_example`, and assert the scanner exits 1. A clean temp dir exits 0. Do not plant a fake key inside `app/`.

## Boundaries

- Always: CI uses mock. A red check blocks merge.
- Ask first: required status checks that need a paid runner, or storing provider keys in GitHub secrets.
- Never: `continue-on-error` on the test or scan steps. Never weaken a test to go green.

## Success criteria

A pull request cannot merge with a failing scan or a failing Playwright run. Local `pnpm build` then the scan exits 0 on the real app.

## Open questions

None.
