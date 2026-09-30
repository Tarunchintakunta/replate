You are the only implementer of Replate. Grok and Gemini do not edit this repo.

The kit is unzipped at ~/Personal/replate-kit. This session’s working directory must be an empty folder, ~/Personal/replate. If you are inside the kit, or inside any Streamline repo, stop and say so.

Read, in this order, before you write code:

1. The kit’s CLAUDE.md
2. AGENT-RULES.md
3. PRD.md
4. CAPABILITY-MAP.md
5. ARCHITECTURE.md
6. DESIGN.md
7. CONSTRAINTS.md
8. Every file in adr/
9. ENV.md, COST-MODEL.md, GITHUB-WORKFLOW.md
10. specs/ that the issue names
11. tasks/plan.md
12. issues/01-scaffold.md

Then do issue 01 only.

- Copy the whole kit into docs/kit/ of the new repo.
- Copy templates/.gitignore, templates/.env.example, and use templates/ci.yml as the shape of the workflow. Issue 01 runs lint and unit tests. Playwright and the secret scan arrive in issues 14 and 15, so a thinner workflow is correct on this first PR if those scripts do not exist yet.
- Create the private GitHub repo with: gh repo create replate --private --source=. --remote=origin --push
- Do that only after .gitignore is committed.
- One branch, microcommits, one pull request. Title and body follow GITHUB-WORKFLOW.md.
- Stop when the pull request is open. Do not start issue 02.

Hard rules:

- No AWS, Google Cloud, or Cloudflare resources.
- No secrets in git, issues, pull requests, logs, or client bundles. Keys belong only in ~/Personal/replate/.env, which I will create later. Do not ask me to paste a key into chat.
- Do not copy ReWords AI copy, color #D97706, assets, or pages.
- Do not add Fal, Replicate, a local FLUX weight, or a dependency that ARCHITECTURE.md does not name.
- If a check fails, fix the cause. Do not skip the test.

Later I will say one of these:

- continue — next issue only, then stop.
- continue through 08 — issues 02 through 08, one pull request each, then stop and print http://localhost:3000.
- continue through 15 — remaining issues, but still stop at 08 if it is not merged yet.

Start issue 01 now.
