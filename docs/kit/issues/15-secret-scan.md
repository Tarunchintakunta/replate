Title: Fail the build when a secret reaches the client

Labels: replate, mvp

Spec: specs/SPEC-proof.md, adr/004-no-secrets-in-client.md

## Why

A public config module is how this category leaks its stack. The scan makes that a failed build.

## Acceptance

- `scripts/secret-scan.ts` implements the patterns in the spec.
- Unit test: a temp file containing `sk_test_example` fails the scanner. A clean dir passes.
- `pnpm build` then the scan exits 0 on this repo.
- CI runs the scan after build and does not set `continue-on-error`.
- Ownership: every image and generation read is covered by an existing test that a second user receives 404. Add the missing test if issue 11 left a gap.
- The final pull request states whether `scripts/smoke-live.ts` was run. If it was not run, say the key was absent. Do not paste the key.

## Verify

```
pnpm test scripts/secret-scan.test.ts
pnpm build
pnpm exec tsx scripts/secret-scan.ts
pnpm exec playwright test
```

## Files

`scripts/secret-scan.ts`, `scripts/secret-scan.test.ts`, `.github/workflows/ci.yml`

## Out of this issue

New features. This is the last v1 slice. After it merges, stop and list the closed issue numbers.
