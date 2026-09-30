# Agent rules

## Order of authority

1. The user’s latest message.
2. `CONSTRAINTS.md` and the ADRs.
3. `PRD.md` and the spec for the issue you are in.
4. `DESIGN.md`.
5. Your own taste. Taste loses.

## How to work an issue

1. Read the issue file and the spec it names.
2. Create the GitHub issue from that file if it does not exist.
3. Branch `issue/<number>-<slug>` from `main`.
4. Write the failing test first when the issue touches logic, credits, OCR parsing, or the editor.
5. Make the smallest change that turns the test green.
6. Microcommit. One concern per commit. Message format is in `GITHUB-WORKFLOW.md`.
7. Run the verify command in the issue. Paste the command and the pass line into the pull request body.
8. Open the pull request. Wait for checks. Squash-merge only when checks are green.
9. Stop after the pull request unless the user already said `continue through 08` or `continue through 15`. Those phrases are defined in `CLAUDE.md`. Always stop at issue 08 and print the local URL before any live provider. Report the PR URL.

## Code

- TypeScript strict. No `any`. No `as` except at a single JSON boundary, with a Zod parse on the other side.
- Validate every request body, every OCR line, and every provider response with Zod.
- Server code performs credit changes inside one database transaction.
- UI calls server actions or route handlers. The browser never calls Fal, WaveSpeed, Gemini, or Replicate directly.
- Comments only for a constraint the code cannot show. No narration comments.
- Match names already in the repo. Do not introduce a second word for the same thing. The words are: image, line, replacement, generation, credit, ledger, provider.

## Design

Follow `DESIGN.md`. No purple gradient, no glass cards, no Inter-only page, no countdown timer, no “50% off” banner, no stock AI sparkles as the logo.

## Testing

- Unit tests live next to the module as `*.test.ts`.
- Playwright lives in `e2e/`.
- Tests must pass with `EDITOR_PROVIDER=mock` and no network.
- A test that needs a real key is a script under `scripts/smoke-live.ts`, skipped in CI, never required for merge.

## GitHub

- Private repository named `replate` under the authenticated user.
- Labels: `replate`, plus `mvp`.
- Do not commit `node_modules`, `.venv`, `.env`, `data/`, `storage/`, or Playwright traces.
- Do not force-push `main`.

## When you are stuck

Stop and write what you tried, the exact error, and the next choice. Do not widen the issue to “fix the platform”. Do not provision a cloud account to get unstuck.
