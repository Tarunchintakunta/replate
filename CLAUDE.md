# Claude Code — Replate

You are the only implementer. Read this file, then `AGENT-RULES.md`, `PRD.md`, `ARCHITECTURE.md`, `DESIGN.md`, `CONSTRAINTS.md`, and `tasks/plan.md` before writing code.

## Mission

Build Replate: a local web app that replaces text already inside a finished image and downloads the result. Ship it as a private GitHub repo with one issue, one branch, and one pull request per slice in `issues/`.

## Hard rules

- Implement issues in numeric order. Do not start issue 05 while issue 04 is open.
- One pull request per issue. Microcommits on the branch. Do not push straight to `main`.
- Tests for the slice are green before the pull request opens.
- Secrets live in `.env` only. `.env` is gitignored. No key, token, or connection string in source, tests, logs, issue bodies, or client JavaScript.
- Do not create AWS, GCP, or Cloudflare resources. Local Mac is the environment. See `adr/001-run-local-not-cloud.md`.
- Do not copy ReWords AI copy, assets, color (`#D97706`), or pages.
- Gemini, Grok, and other chat models do not write or edit this repository. If a draft appears from another model, rewrite it yourself and do not merge it as-is.
- The browser bundle may contain only `NEXT_PUBLIC_` values that are safe to show a stranger. Provider keys, database URLs, and webhook secrets are server-only. See `adr/004-no-secrets-in-client.md`.
- Ask before adding a dependency that is not in `ARCHITECTURE.md`, before any paid API call beyond a single manual smoke test, and before opening the repo to public.

## Definition of done for the product

All of these are true on this Mac:

1. `pnpm install`, `pnpm test`, `pnpm exec playwright test`, and `pnpm build` succeed.
2. `pnpm dev` opens a workspace. Upload, detect or draw, replace, download.
3. A new user has 10 trial credits. One standard image costs 10. A failed generation leaves the balance unchanged.
4. With no API keys, mock mode still completes the path and the downloaded file differs from the upload.
5. With `GEMINI_API_KEY`, setting the provider to `gemini` returns a real edit.
6. The GitHub repo has a closed issue and a merged pull request for every file in `issues/`.

## First action

If this folder is not yet a git repo, follow issue 01 exactly. Copy this kit into `docs/kit/` of the repo so later sessions can see it. Then stop and open the pull request.

Later messages mean exactly this:

- `continue` — do the next issue only, then stop.
- `continue through 08` — do issues 02 through 08, one pull request at a time, then stop and print the local URL. Do not start 09.
- `continue through 15` — do the remaining issues one pull request at a time. If 08 is not merged yet, stop at 08 anyway and print the URL.

Never skip a number. Never start 09 before the user has seen the mock app.
