# Spec: billing

Module id: `billing`. Depends on `auth`, `credits`. It does not import the editor.

## Objective

A test-mode Stripe Checkout pack adds 100 credits after a signed webhook. The $5 figure is a test fixture, not a launch price.

## Commands

```
pnpm test lib/billing/webhook.test.ts
```

No live Stripe call is required to merge.

## Project structure

```
lib/billing/checkout.ts
lib/billing/webhook.ts
lib/billing/webhook.test.ts
app/api/billing/checkout/route.ts
app/api/billing/webhook/route.ts
app/pricing/page.tsx
db migration: stripe_events (id text primary key, received_at)
```

## Behavior

`POST /api/billing/checkout` requires a session. It creates a Checkout Session in test mode for `STRIPE_PRICE_PACK`, quantity 1, metadata `userId`. Success and cancel URLs are `${APP_URL}/`.

`POST /api/billing/webhook` reads the raw body and verifies `Stripe-Signature` with `STRIPE_WEBHOOK_SECRET`. Invalid signature returns 400 and writes nothing.

On `checkout.session.completed`, if `stripe_events.id` already contains the event id, return 200 and do not insert another ledger row. Otherwise insert the event id and a ledger row `delta = 100`, `reason = stripe_pack`, `stripe_event_id` set, in one transaction.

Ignore other event types with 200.

`/pricing` is one screen. It says `100 credits` and `test price $5`. No crossed-out price, no countdown, no annual plan. The button says `Buy 100 credits`. If Stripe env is empty, the button is disabled and the page says `Payments are off until test keys are set.`

The desk gains a text link `Credits` to `/pricing`. It does not become a storefront.

## Testing strategy

Construct the event with Stripe’s test header helper, or with the library’s documented constructEvent path against a fixture secret `whsec_test_fixture_not_a_real_secret`. Assert:

- Valid event moves a user from 10 to 110.
- The same event id a second time stays 110.
- A bad signature leaves the ledger unchanged.

Do not put a live `sk_live` or a real `sk_test` in the test file. The fixture secret string above is a label, not a credential.

## Boundaries

- Always: verify the webhook signature. Store the event id.
- Ask first: a second product, subscription billing, or live-mode keys.
- Never: collect card numbers in our inputs. Checkout is the only card UI. Never call the image editor from this module.

## Success criteria

The three webhook assertions pass with no network. `/pricing` renders the plain numbers.

## Open questions

None. Creating the Stripe test price in the dashboard is a human step, written in `ENV.md`. The code reads `STRIPE_PRICE_PACK`.
