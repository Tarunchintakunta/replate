Title: Scaffold the Replate repo

Labels: replate, mvp

Spec: specs/SPEC-proof.md (lint and unit job only)

## Why

Every later slice needs a private repo, a lockfile, and the kit living at `docs/kit/` so a new session can read the rules.

## Acceptance

- Next.js 15 App Router, React 19, TypeScript strict, Tailwind v4, Zod, Biome, Vitest, pnpm, Node 22. Versions pinned by the lockfile.
- `templates/.gitignore` and `templates/.env.example` are copied to the repo root and match the kit.
- This whole kit is copied to `docs/kit/`. Edits to product rules happen in the kit first, then the copy.
- A Vitest test asserts `1 + 1 === 2` so `pnpm test` has a real pass. Replace it when issue 03 adds real tests. Do not leave a skipped test.
- Labels `replate` and `mvp` exist.
- Private GitHub repo `replate`, created only after the first commit and the gitignore are in place.
- A workflow that runs `pnpm lint` and `pnpm test` on pull requests. Playwright and the secret scan wait for issues 14 and 15.
- `CLAUDE.md` at the repo root is the same text as `docs/kit/CLAUDE.md`.

## Verify

```
pnpm lint
pnpm test
gh repo view --json name,visibility
```

Visibility must be `PRIVATE`.

## Files

`package.json`, `pnpm-lock.yaml`, `tsconfig.json`, `biome.json`, `next.config.ts`, `app/layout.tsx`, `app/page.tsx`, `.gitignore`, `.env.example`, `.github/workflows/ci.yml`, `docs/kit/**`, `CLAUDE.md`

## Out of this issue

Upload, OCR, providers, auth, Stripe, AWS, and any API key. Do not run a live model. Stop after the pull request.
