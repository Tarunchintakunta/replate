Title: Build on a many-core host without a migration race

Labels: replate, mvp

Spec: adr/006-hosted-copy.md

## Why

`next build` collects page data in one worker per core. Every worker imports `db/client.ts`, which migrates the database on load. On Railway's 17 workers two of them created the same table at once and the build failed with "table `credit_ledger` already exists". On this Mac the same race showed up as "database is locked".

## Acceptance

- Many processes opening one new database all come up.
- The Railway build passes.

## Verify

Start 16 processes that import `db/client.ts` against one new file; all succeed. Railway's build log ends in a successful deploy.

## Files

`db/client.ts`
