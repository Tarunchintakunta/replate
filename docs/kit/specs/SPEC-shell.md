# Spec: shell

Module id: `shell`. Depends on nothing.

## Objective

The app opens on a proofing desk. `/` is the workspace, not a marketing page. Empty state, tokens, and type are in place before any upload works.

User: the builder, on this Mac, at a 1280px window and a 390px window.

## Commands

```
pnpm dev
pnpm lint
pnpm test
pnpm exec playwright test e2e/shell.spec.ts
```

## Project structure

```
app/layout.tsx          fonts, paper background, metadata title Replate
app/page.tsx            empty workspace
app/globals.css         the tokens below, and only these colors
components/TopBar.tsx
components/Workspace.tsx
e2e/shell.spec.ts
```

## Code style

CSS variables, used by Tailwind v4 `@theme`. Do not scatter hex in components.

```css
:root {
  --paper: #f3efe6;
  --ink: #1c1915;
  --green: #0e6b52;
  --wash: #e5f2ec;
  --rule: #d9d2c5;
  --danger: #8f2d2d;
}
```

Fonts, through `next/font`: Newsreader (wordmark, italic), IBM Plex Sans (UI), IBM Plex Mono (credit count only).

Wordmark text is `Replate`. The only subtitle is `Change the words. Keep the picture.`

## Testing strategy

Playwright checks the wordmark, the drop copy, the credit slot, and that the layout stacks under 800px. A screenshot is not the test. The test asserts accessible names and the drop text.

## Boundaries

- Always: follow `DESIGN.md`. Focus ring uses `--green`.
- Ask first: adding Radix or any component kit. v1 shell needs neither.
- Never: a countdown, a gradient, a sparkle icon, Inter as the only face, or a homepage that sits in front of the desk.

## Success criteria

- `pnpm dev` serves `/` with the empty drop area “Drop a PNG, JPG, or WebP.”
- At 1280px the bar is 56px and the page is two columns, about 60/40.
- At 390px the image region is above the lines region.
- Body text contrast of ink on paper is above 7:1.
- No purple, no glass, no “powered by AI”.

## Open questions

None. Tokens are closed.
