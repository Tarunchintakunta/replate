# Constraints — Replate

These are the quality bar. A pull request that breaks one does not merge.

## Always

- Typecheck, Biome, unit tests, and Playwright are clean for the slice.
- Credit mutation is transactional and happens after the PNG is on disk.
- Upload path re-encodes through sharp and drops EXIF.
- Provider calls happen on the server, with a 60s timeout.
- New code has a test when it decides money, parsing, or file acceptance.
- UI matches `DESIGN.md` tokens. Use the CSS variables, do not scatter hex.

## Ask first

- A new npm or pip dependency that is not named in `ARCHITECTURE.md`.
- Any cloud account, bucket, or deploy.
- Turning the GitHub repo public.
- Spending more than one live generation to debug. The mock provider is for debugging.
- Changing the credit price away from 10 per standard image.

## Never

- Commit or print secrets. A client bundle that contains `GEMINI_API_KEY`, `WAVESPEED_API_KEY`, `STRIPE_SECRET`, `AUTH_SECRET`, or a database URL is a failed build.
- Copy text or images from rewordsai.app into this repo.
- Debit credits before the provider returns an image.
- Fetch a URL the user typed. v1 accepts uploads only. This blocks SSRF.
- Store card numbers. Stripe Checkout is the only card UI.
- Add a fake discount timer.
- Disable a failing test to go green.
- Run FLUX or any multi-gigabyte weight on this Mac as part of v1.

## Performance bar for v1

- Workspace interactive in under 2s on localhost after compile.
- OCR of a 1 megapixel fixture under 5s on this Mac.
- Mock generation under 2s.
- Live generation may take as long as the vendor, capped at 60s, then fail cleanly.

## Security bar

- Max upload 8 MB.
- Accepted types: PNG, JPEG, WebP, checked by magic bytes after the multipart parse.
- Output long edge 1024 for v1 provider calls.
- Session cookie `httpOnly`, `sameSite=lax`, `secure` in production.
- Rate limit generation to 10 attempts per user per hour in app code, even on localhost, so a loop cannot drain a live key.
- Ownership check on every image and generation read.
