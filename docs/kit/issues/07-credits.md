Title: Add the credit ledger and the trial grant

Labels: replate, mvp

Spec: specs/SPEC-credits.md

## Why

Credits are the product’s money. They need tests before a button can spend them.

## Acceptance

- `grantTrial` inserts +10 once.
- `debitGeneration` inserts −10 or throws without writing.
- Rollback leaves the sum unchanged.
- `GET /api/credits` returns the sum.
- The top bar reads that endpoint instead of the static `10` from issue 02.
- No editor import in `lib/credits/`.

## Verify

```
pnpm test lib/credits/ledger.test.ts
```

## Files

`lib/credits/ledger.ts`, `lib/credits/ledger.test.ts`, `app/api/credits/route.ts`, `components/TopBar.tsx`

## Out of this issue

Stripe. Charging on generate. That coupling is issue 08.
