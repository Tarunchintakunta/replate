# Plan

Order is the issue number. Do not parallelize. Each slice is one session and one pull request.

| # | Slice | Done when |
|---|---|---|
| 01 | Scaffold, gitignore, CI skeleton, copy this kit to `docs/kit` | `pnpm lint` and `pnpm test` run, repo is private on GitHub |
| 02 | Tokens, font, empty workspace shell | Page matches `DESIGN.md` at 1280 and 390 widths |
| 03 | Drizzle schema, migrations, storage adapter | Unit test writes and reads a PNG from disk and a row from SQLite |
| 04 | Upload route and workspace preview | Bad bytes are rejected. A real PNG previews |
| 05 | OCR sidecar and line list | Fixture PNG yields at least one line, or a drawn box can stand in |
| 06 | `ImageEditor` and mock | Mock output differs from input and is a valid PNG |
| 07 | Ledger and trial grant | New user balance is 10. Debit refuses at 0 |
| 08 | Generation route and download | Playwright happy path on mock, balance ends at 0 |
| 09 | Gemini provider | Adapter test with a mocked HTTP response. Live call only if the key exists |
| 10 | WaveSpeed provider | Same, model id `wavespeed-ai/flux-kontext-pro` |
| 11 | Dev session and optional Google | Playwright signs in as the dev user without Google |
| 12 | Stripe test pack | Webhook fixture adds 100 credits. No live key required |
| 13 | Failure path | Provider throw does not change the ledger. Button disabled at 0 |
| 14 | CI complete | Actions green on the PR |
| 15 | Security pass | Secret scan fails the build if a key shape appears in client output |
| 16 | Local editor | `EDITOR_PROVIDER=local` makes a real edit with no key. `eval.py` holds a mean overlap of 0.5 |
| 17 | Local credits | The local user refills from `/pricing`. The local editor is not rate limited |
| 18 | Desk polish | Upload detects by itself, a second picture needs no reload, the phone layout fits, OCR reads a headline whole |
| 19 | Container | `docker build .` runs the full loop with data on a volume, ready for a container host |
| 20 | Migration race | Parallel build workers open one new database without failing |
| 21 | Postgres and accounts | Neon holds the data; people sign up with a username and password |

Issues 09 and 10 are adapters behind the interface from 06. They do not change the UI except the provider pill.

Checkpoint after issue 08: the product is usable with zero cloud cost. Stop and show the user the local URL before continuing to live providers.
