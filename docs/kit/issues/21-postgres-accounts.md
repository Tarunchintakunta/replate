Title: Move to Neon Postgres with username and password accounts

Labels: replate, mvp

Spec: adr/007-postgres-and-passwords.md

## Why

The builder asked for Neon as the database and for a plain username and password sign-in in place of Google.

## Acceptance

- Every query runs on Postgres through Drizzle. `DATABASE_URL` is a Neon URL on Railway and on this Mac.
- Tests and CI run on an in-process Postgres with no network.
- A visitor can create an account, sign out, and sign back in. A wrong password and a taken name show a plain message. A new account gets the 10-credit trial.
- Passwords are stored as salted scrypt hashes. Sign-in errors never say which of the two fields was wrong.
- Google sign-in is gone. The local button still works on `http://localhost:3000` only.
- A session whose user no longer exists shows the sign-in page.
- With the `local` editor, any signed-in user can add 100 free credits.

## Verify

```
pnpm test
pnpm exec playwright test
pnpm build
```

## Files

`db/`, `lib/auth/users.ts`, `src/auth.ts`, `src/components/SignIn.tsx`, `src/app/page.tsx`, every route that queries, tests beside each, `e2e/account.spec.ts`, `Dockerfile`, `package.json`, ADR 007
