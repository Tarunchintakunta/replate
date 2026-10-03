Title: A landing page, sign-in and sign-up pages, and a dashboard

Labels: replate, mvp

Spec: DESIGN.md

## Why

The builder asked for an animated landing page, separate sign-in and sign-up pages, and a dashboard. Sign-in also failed on the Vercel address: Next.js refused the form post because its origin was the Vercel domain while the request reached Railway.

## Acceptance

- `/` explains the product with a live demo and a real before and after from the local editor, and links to sign up or, when signed in, to the dashboard.
- `/signin` and `/signup` are separate pages. Errors show in plain words. A signed-in visitor is sent to `/dashboard`.
- `/dashboard` is the desk and needs a session; without one it sends the visitor to `/signin`.
- Sign out returns to `/`.
- Motion is CSS only and stops under `prefers-reduced-motion`. No horizontal scroll at 375px.
- `ALLOWED_ORIGINS` lists front domains whose form posts Next.js accepts.

## Verify

```
pnpm test
pnpm exec playwright test
pnpm build
```

## Files

`src/app/page.tsx`, `src/app/signin`, `src/app/signup`, `src/app/dashboard`, `src/components/AuthPage.tsx`, `src/components/landing/`, `src/app/globals.css`, `public/demo/`, `next.config.ts`, `Dockerfile`, e2e specs, `DESIGN.md`
