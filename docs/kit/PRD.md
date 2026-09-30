# PRD — Replate

Status: approved for Claude to build. Date: 2026-09-30.

## Objective

Replate replaces words that are already painted into a finished image. The user does not have the source file, the font file, or Photoshop. They upload a picture, choose the line, type the new words, and download a new picture that tries to keep the font, color, perspective, and background.

The person using v1 is the builder, on this Mac, proving the loop before any customer exists. The product still behaves like a real single-user web app so the same code can take a second user later without a rewrite.

## Why this shape

The category already exists. ReWords AI, PhoText, EditTextImage, and several credit-pack sites do this job by calling a hosted image-edit model and charging credits. Their fixed hosting cost is small. The cost that matters is the model call, about $0.01 to $0.04 per successful edit in 2026, plus retries.

Replate v1 exists to make that loop real on this machine:

- OCR on the Mac, so detection does not need a cloud bill.
- One server-side editor interface, so mock, Gemini, and WaveSpeed are interchangeable.
- Credits that move only after a successful file is stored.
- A test suite that proves the path with no API key.

## User story

As a person with a finished PNG, JPG, or WebP, I can change one or more lines of text and download the result, and I can see that a failed attempt did not spend my credits.

## In scope for v1

- Local web app, desktop and a usable narrow window.
- Upload PNG, JPG, WebP up to 8 MB. Long edge above 2048 pixels is scaled down before the editor sees it.
- OCR lines with boxes. Click a line, or draw a box when OCR misses.
- Type a replacement. Empty replacement means “remove this text and rebuild the background.”
- One generation covers every selected line.
- Download the result as PNG.
- Trial balance of 10 credits. Standard output costs 10 credits. Balance is per local user.
- History of the last 20 generations on this machine.
- Providers: `mock` (default), `gemini`, `wavespeed`.
- Dev login with no Google key. Google login when the Google client id and secret exist.
- Stripe test-mode checkout for a single credit pack, after the edit loop works.

## Out of scope for v1

- AWS, GCP, Cloudflare, GPU instances, and self-hosted FLUX.
- 2K and 4K outputs. They multiply provider cost. Add them only after 1K is solid.
- Accounts for a team, seats, or admin dashboards.
- The 11-language SEO site, comparison pages, and browser extension.
- Translation of a whole poster as a separate product. The user types the new words.
- Batch of many files.
- Public API.
- Mobile native apps.
- Claiming the font is a perfect match. The UI says the match is best-effort.

## Success criteria

- Playwright completes upload → detected or drawn text → replace → download on `EDITOR_PROVIDER=mock` with credits going from 10 to 0.
- A second run with an empty balance is rejected before any provider call.
- Killing the provider (mock throws) leaves the balance at 10 and shows an error.
- `pnpm build` succeeds.
- No secret string from `.env.example` keys appears in `.next/static` or any client chunk.
- A manual smoke note in the final PR says whether Gemini was actually called, and the result was a real image or not yet, because the key may be absent.

## Assumptions

- The builder has a Mac with Apple Silicon (M5 Pro), Node 22, pnpm, Python 3.12, and GitHub `gh` authenticated.
- Chat subscriptions for Claude, Gemini, and Grok are not API keys. Live image edit needs `GEMINI_API_KEY` from Google AI Studio, or `WAVESPEED_API_KEY`.
- v1 has one human user. Dev login is enough until Google keys are pasted.
- Legal entity, domain, and production host are later. The product name in the UI is Replate.

## Non-goals that look tempting

- Running FLUX Kontext on the laptop. The Pro model is an API. A local open weight will not match it and will consume days.
- Copying ReWords’ pricing page, flash sale, or locale farm to “launch faster.”
- Putting provider names and default model strings into a client config module. That leak is how their stack became public. Server env only.
