Title: Add a Stripe test pack of 100 credits

Labels: replate, mvp

Spec: specs/SPEC-billing.md

## Why

The ledger needs one honest way to gain credits after the trial, still with no live charges.

## Acceptance

- Checkout route and signature-checked webhook.
- `stripe_events` makes the same event id a no-op.
- Valid test event adds exactly 100. Bad signature adds 0.
- `/pricing` shows `100 credits` and `test price $5` with no discount theater.
- The desk links to it. Billing code does not import the editor.
- Tests use the fixture signing secret named in the spec, not a real key.

## Verify

```
pnpm test lib/billing/webhook.test.ts
pnpm exec playwright test e2e/pricing.spec.ts
```

## Files

`lib/billing/checkout.ts`, `lib/billing/webhook.ts`, `lib/billing/webhook.test.ts`, `app/api/billing/checkout/route.ts`, `app/api/billing/webhook/route.ts`, `app/pricing/page.tsx`, a migration for `stripe_events`, `e2e/pricing.spec.ts`

## Out of this issue

Live mode, subscriptions, and a second pack. Do not create Stripe resources from the API beyond a Checkout Session when the human has set test keys. Merging does not require those keys.
