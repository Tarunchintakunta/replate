Title: Keep the local user working past the trial

Labels: replate, mvp

Spec: specs/SPEC-credits.md

## Why

The trial is 10 credits and one image costs 10. With Stripe keys absent, the local user is locked out after one edit. The local editor also has no paid key behind it, so the hourly attempt limit protects nothing there.

## Acceptance

- `/pricing` shows `Add 100 local credits` to the passwordless local user on `http://localhost:3000`, and to nobody else.
- `POST /api/credits/local` adds 100 with reason `adjust` in one transaction, then returns to the desk. Any other user or origin gets 403. No session gets 401.
- The trial stays 10 and an image still costs 10.
- The 10-per-hour attempt limit still applies to `mock`, `gemini`, and `wavespeed`. It does not apply to `local`.
- Unit tests cover the grant, the guard, and the limit exemption. Playwright adds 100 from the pricing page.

## Verify

```
pnpm test lib/credits lib/auth lib/generation
pnpm exec playwright test e2e/topup.spec.ts
```

## Files

`lib/credits/ledger.ts`, `lib/auth/users.ts`, `src/app/api/credits/local/route.ts`, `src/app/pricing/page.tsx`, `lib/generation/run.ts`, tests beside each, `e2e/topup.spec.ts`

## Out of this issue

Changing the price or the trial. Free credits for Google sign-ins. Stripe.
