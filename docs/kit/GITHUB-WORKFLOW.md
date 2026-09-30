# GitHub workflow

## Repo

Create a new **private** repository named `replate`. Do not push to Streamline, and do not use the Streamline remote.

```
gh repo create replate --private --source=. --remote=origin --push
```

Run that only after issue 01 has a real commit and `.gitignore` is in place.

## Issues

For each file in `issues/`, create the GitHub issue with the title and body. Label `replate` and `mvp`. Do this at the start of the slice, not all at once in a burst that you then ignore. The body of the issue is the contract.

## Branches and commits

Branch: `issue/03-storage` from fresh `main`.

Commit subjects:

```
feat: store uploaded pngs on local disk
test: reject a file that is not an image
fix: roll back the row when sharp throws
```

Rules:

- Subject line under 72 characters, imperative, no period.
- The body says why, in one or two lines, when the subject is not enough.
- One concern per commit. A commit that formats the world plus adds a feature is two commits. Format only the lines you touched.
- Push the branch after every green commit: `git push -u origin HEAD`.
- Do not commit on `main`.

## Pull requests

Title matches the issue: `Store uploads in SQLite and on disk (#3)`.

Body:

```
Closes #3

What changed
- ...

Verify
- pnpm test
- result: pass, N tests

Not in this PR
- ...
```

Squash-merge when GitHub checks are green. Delete the branch.

## Checks

GitHub Actions on pull requests:

- `pnpm lint`
- `pnpm test`
- `pnpm exec playwright test`
- `pnpm build`
- secret scan of the build output

CI uses `EDITOR_PROVIDER=mock`. It does not receive API keys. Repository secrets are not required for v1.

## Definition of a finished slice

The issue is closed by the merged PR, `main` is green, and the next issue has not been started in that same push.
