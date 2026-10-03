Title: Detect again after a result, and harden sign-in

Labels: replate, mvp

Spec: adr/007-postgres-and-passwords.md

## Why

A review of the Postgres and accounts work found three defects:

- **Detect again fails.** Pressing Detect Text on an image that already has a result returned 500. A saved replacement points at the OCR line it changed, and the route deletes and rewrites those lines.
- **The failure counter has no bound.** The failed sign-in counter took any string as a key, so a script sending huge random usernames could grow the server's memory without limit.
- **Local login fails open.** A production deploy that forgot `APP_URL` fell back to `http://localhost:3000`, which turns on the passwordless local login.

## Acceptance

- Detecting again on an image with a past result succeeds. The result keeps its own copy of the box; its link to the old line becomes empty.
- A malformed username is refused without a lookup and is not counted. The counter is swept once it holds 10,000 names.
- The local button is off in any production build, whatever `APP_URL` says.

## Verify

```
pnpm test __tests__/redetect.test.ts lib/auth
pnpm exec playwright test
```

## Files

`db/schema.ts`, `db/migrations/0001_ocr_line_set_null.sql`, `src/auth.ts`, `lib/auth/users.ts`, `__tests__/redetect.test.ts`, `lib/auth/current-user.test.ts`, `README.md`
