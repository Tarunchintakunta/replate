# Environment

Create `.env` in the app repo. Never commit it. Copy from `.env.example`.

```
EDITOR_PROVIDER=mock
OCR_MODE=rapid
APP_URL=http://localhost:3000
AUTH_SECRET=generate-a-long-random-string
DATABASE_URL=file:./data/replate.db

# Optional. Without this, the app stays on the mock editor.
GEMINI_API_KEY=
GEMINI_IMAGE_MODEL=gemini-2.5-flash-image

# Optional quality provider. Leave empty until you want a $0.04 test.
WAVESPEED_API_KEY=
WAVESPEED_EDIT_MODEL=wavespeed-ai/flux-kontext-pro

# Optional. Dev login works with neither set.
AUTH_GOOGLE_ID=
AUTH_GOOGLE_SECRET=

# Optional. Billing issue only. Test mode secret, test mode price.
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PRICE_PACK=
```

## How to get a key

- Gemini: Google AI Studio, create an API key. The Gemini chat subscription does not fill this in for you.
- WaveSpeed: wavespeed.ai account, API key. One test image is about $0.04.
- Google login: a Google OAuth client whose redirect is `http://localhost:3000/api/auth/callback/google`.
- Stripe: test mode secret key and a test price. Card number `4242 4242 4242 4242`. No live mode in v1.

## How Claude receives them

You write `.env` on the Mac. Claude reads that file when it runs the app. Do not paste the values into the prompt, an issue, or a pull request. If a command prints the env, stop and scrub the scrollback.

## AWS

There is no AWS key in v1. Do not create one for this project until a later ADR.
