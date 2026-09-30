# Cost model

Figures are public list prices around September 2026. Confirm on the vendor page before a long run.

## This Mac, v1

| Item | Monthly |
|---|---|
| Next.js, SQLite, disk, RapidOCR | $0 |
| Domain, AWS, GCP | $0 until a later ADR |
| Mock and Playwright | $0 |

## One successful 1K edit

| Provider | About |
|---|---|
| mock | $0 |
| Gemini 2.5 Flash Image | about $0.04 per image |
| WaveSpeed FLUX Kontext Pro | $0.04 per run |
| GPT Image low quality, if added later | about $0.01 |
| A retry | the same amount again |

OCR on device is effectively free. Stripe test mode is free. A real Stripe charge later is 2.9% + $0.30, which hurts a $5 pack more than a subscription.

## What Replate charges in the product

Trial: 10 credits, one standard image.
Later pack: decide after the loop works. Do not copy a crossed-out “50% off” price. A sane test price is one pack of 100 credits (10 images) in Stripe test mode so the ledger can be proven. The dollar amount on that test price can be $5. It is not a public launch price.

## Rule for Claude

Debug on `mock`. One live call to confirm a provider. Do not loop a live provider to chase font quality. That is how a test session becomes a $20 bill for the same poster.
