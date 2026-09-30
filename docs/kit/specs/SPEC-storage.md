# Spec: storage

Module id: `storage`. Depends on nothing.

## Objective

SQLite holds rows. The Mac disk holds PNGs. The public URL is never a filesystem path.

## Commands

```
pnpm db:migrate
pnpm test lib/images/store.test.ts
```

## Project structure

```
db/schema.ts
db/migrations/
db/client.ts              better-sqlite3, path from DATABASE_URL
lib/images/store.ts       writePng, readPng, key for originals and generations
lib/images/store.test.ts
data/                     gitignored database
storage/originals/        gitignored
storage/generations/      gitignored
```

## Code style

```ts
export function originalKey(imageId: string): string {
  return `originals/${imageId}.png`
}

export function generationKey(generationId: string): string {
  return `generations/${generationId}.png`
}
```

Ids are UUID v4. Keys are relative. `readPng` joins them under `storage/` and rejects `..`.

Tables, matching `ARCHITECTURE.md`:

- `users` — id, email unique, name, created_at
- `images` — id, user_id, width, height, storage_key, created_at
- `ocr_lines` — id, image_id, text, confidence, x, y, width, height
- `generations` — id, user_id, image_id, provider, model, status, output_key nullable, error nullable, created_at
- `generation_replacements` — generation_id, ocr_line_id nullable, from_text, to_text, x, y, width, height
- `credit_ledger` — id, user_id, delta integer, reason, generation_id nullable, stripe_event_id nullable, created_at

`status` is `pending`, `succeeded`, or `failed`. Balance is `sum(delta)`. No balance column.

`sessions` arrives with auth. `stripe_events` arrives with billing. Do not create them in the first migration if those modules are not in the issue.

## Testing strategy

Vitest uses a temp directory and a temp sqlite file. One test writes a 1×1 PNG and reads the same bytes back. One test rejects a key that contains `..`.

## Boundaries

- Always: parameterized SQL through Drizzle. Foreign keys on.
- Ask first: switching off SQLite, adding Postgres, or putting files in S3.
- Never: serve `storage/` as a static directory. Never commit `data/` or `storage/`.

## Success criteria

- `pnpm db:migrate` creates the file at `DATABASE_URL`.
- A row and a PNG round-trip in the unit test.
- A path traversal key throws.

## Open questions

None.
