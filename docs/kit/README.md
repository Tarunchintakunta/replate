# Replate

Change the words. Keep the picture.

This folder is the build kit. It is not the app. Claude Code creates the app from these files in a new private repository. Do not build Replate inside the Streamline repo.

## What you do

1. Unzip this kit somewhere that is not the git repo. A good place is `~/Personal/replate-kit`.
2. Open Claude Code in a new empty folder, `~/Personal/replate`.
3. Paste the prompt in `prompts/CLAUDE-START.md`.
4. After the first pull request, reply `continue through 08`. Claude stops and gives you `http://localhost:3000`. Use the app. Then reply `continue through 15`.
5. When a later issue needs a key, put it only in `~/Personal/replate/.env`. Never paste keys into GitHub, issues, or chat.

The zip on the Desktop stays the source of the decisions. Claude copies the kit docs into the repo as part of issue 01 so the rules travel with the code.

## What is in the kit

| Path | Role |
|---|---|
| `PRD.md` | What v1 is |
| `CAPABILITY-MAP.md` | Modules and build order |
| `specs/` | One spec per module |
| `issues/` | Fifteen GitHub issue bodies, in order |
| `adr/` | Local Mac, Claude only, one editor interface, no secrets in the client |
| `DESIGN.md` | Visual rules |
| `ARCHITECTURE.md` | Stack, schema, provider contract |
| `CONSTRAINTS.md` | Always, ask first, never |
| `templates/` | `.gitignore`, `.env.example`, CI shape |
| `prompts/CLAUDE-START.md` | The message you paste into Claude Code |

## Decisions already made

| Topic | Decision |
|---|---|
| Product name | Replate |
| Who writes code | Claude only |
| Where v1 runs | This Mac (Apple M5 Pro). Not AWS. Not Google Cloud. |
| OCR | RapidOCR on the Mac |
| Real image edit | Gemini image edit first, because an API key is the one you can create today. WaveSpeed FLUX Kontext Pro is the quality provider after that key exists. |
| Tests with zero keys | A mock editor. Playwright must pass with no network and no secrets. |
| AWS | Forbidden until the local loop works, and then only after you say yes |

## What “100% working” means

A person can upload a PNG, JPG, or WebP, see the words (or draw a box), type the replacement, and download a new image. Credits fall only when that generation succeeds. `pnpm test` and `pnpm exec playwright test` pass on the mock provider. With `GEMINI_API_KEY` set, the same screen calls Gemini. With `WAVESPEED_API_KEY` set, the same screen can call FLUX Kontext Pro.

## What this product is not

Replate is an original product in the same category as ReWords AI. Do not copy their name, colors, marketing sentences, screenshots, page farm, or code. Do not ship a fake countdown sale.
