# Spec: auth

Module id: `auth`. Depends on `storage`.

## Objective

A session identifies the user. On localhost a single button is enough. Google is optional and off until its env vars exist.

## Commands

```
pnpm test lib/auth/current-user.test.ts
pnpm exec playwright test e2e/login.spec.ts
```

## Project structure

```
auth.ts                         Auth.js config
app/api/auth/[...nextauth]/route.ts
lib/auth/current-user.ts
components/Account.tsx
```

## Behavior

Bootstrap, used by issues 04 through 08 before this issue merges: `currentUser()` returns a row email `local@replate.test`, creating it and granting the trial inside one transaction if missing. That is a temporary function. This issue replaces the implicit bootstrap with a real session, and keeps the same email so the ledger is not granted twice.

Dev login: one button, `Continue as local`. It signs in `local@replate.test` through an Auth.js credentials provider with no password. A server component renders that button only when `APP_URL` is exactly `http://localhost:3000`. A deployed URL does not get the button. `NODE_ENV=production` on localhost still shows it, so `pnpm start` and CI can sign in.

Google provider is registered only when both `AUTH_GOOGLE_ID` and `AUTH_GOOGLE_SECRET` are non-empty. Redirect the user will configure later: `http://localhost:3000/api/auth/callback/google`. Do not block the slice on Google.

Cookie: `httpOnly`, `sameSite=lax`, `secure` only when the app URL is https.

`currentUser()` reads the session. No session returns null. Routes that need a user respond 401.

New Google users get `grantTrial` once, same as the local user.

Sign out clears the session and returns to `/`, which shows the button again.

## Testing strategy

Playwright signs in with `Continue as local` and sees the balance. It does not call Google. A unit test asserts `grantTrial` does not run a second time for `local@replate.test`.

## Boundaries

- Always: server-side session checks on image and generation reads.
- Ask first: passwords, email magic links, or a user table rewrite.
- Never: a shared unlimited-credit backdoor. Never put `AUTH_SECRET` in the client bundle.

## Success criteria

- Playwright reaches the desk only after the local button.
- With `APP_URL` set to any non-localhost origin, the HTML of `/` does not contain `Continue as local`.
- Existing trial balance for `local@replate.test` stays a single +10 row.

## Open questions

None. Google keys are optional.
