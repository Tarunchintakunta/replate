Title: Build the empty proofing desk

Labels: replate, mvp

Spec: specs/SPEC-shell.md

## Why

The product is the desk. Tokens and layout land before data, so later slices do not invent a second visual language.

## Acceptance

- `/` shows the wordmark `Replate`, the line `Change the words. Keep the picture.`, and `Drop a PNG, JPG, or WebP.`
- Colors come only from the CSS variables in the spec. Fonts are Newsreader, IBM Plex Sans, and IBM Plex Mono.
- Top bar is 56px and includes a credit slot reading `10` (static until issue 07) and a provider pill `Local preview`.
- Two columns at 1280px. Stacked at 390px.
- Visible green focus ring on the drop area.
- No marketing page, no gradient, no sparkle, no countdown.

## Verify

```
pnpm lint
pnpm test
pnpm exec playwright test e2e/shell.spec.ts
```

## Files

`app/layout.tsx`, `app/page.tsx`, `app/globals.css`, `components/TopBar.tsx`, `components/Workspace.tsx`, `e2e/shell.spec.ts`

## Out of this issue

A working upload. The drop area may be inert. The credit number is allowed to be static until the ledger exists.
