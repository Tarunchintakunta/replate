Title: Store rows in SQLite and PNGs on disk

Labels: replate, mvp

Spec: specs/SPEC-storage.md

## Why

Images and the ledger need a home that works with no cloud account.

## Acceptance

- Drizzle schema and a migration for the tables in the spec, except `stripe_events`.
- `pnpm db:migrate` creates `data/replate.db` from `DATABASE_URL`.
- `originalKey` and `generationKey` as specified. `..` throws.
- Unit test writes and reads a PNG in a temp directory and inserts a row in a temp database.
- `data/` and `storage/` are gitignored and not in the commit.

## Verify

```
pnpm db:migrate
pnpm test lib/images/store.test.ts
```

## Files

`db/schema.ts`, `db/client.ts`, `db/migrations/*`, `lib/images/store.ts`, `lib/images/store.test.ts`, `package.json` script `db:migrate`

## Out of this issue

HTTP upload routes. Auth.js tables. Those are later issues.
