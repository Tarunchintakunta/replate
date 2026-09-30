Title: Require a session and keep the local button

Labels: replate, mvp

Spec: specs/SPEC-auth.md

## Why

The bootstrap user was a bridge. A session is the real boundary, without blocking on Google.

## Acceptance

- Auth.js session. Cookie flags as in the spec.
- `Continue as local` signs in `local@replate.test` only when `APP_URL` is `http://localhost:3000`. Any other origin’s HTML does not contain that button. Localhost production mode still shows it.
- The existing trial row is not duplicated.
- Image and generation routes return 401 without a session and 404 for another user’s id.
- Google provider is wired only when both env vars are set. Tests do not call Google.
- Playwright signs in, then completes the mock replace path.

## Verify

```
pnpm test lib/auth/current-user.test.ts
pnpm exec playwright test e2e/login.spec.ts e2e/replace.spec.ts
```

## Files

`auth.ts`, `app/api/auth/[...nextauth]/route.ts`, `lib/auth/current-user.ts`, `components/Account.tsx`, `e2e/login.spec.ts`

## Out of this issue

Passwords, email login, and a user admin screen.
