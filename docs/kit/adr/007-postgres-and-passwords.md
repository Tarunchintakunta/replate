# ADR 007 — Postgres on Neon, and username and password accounts

Date: 2026-10-02. Status: accepted. Supersedes the database and sign-in parts of ADR 006.

## Decision

The database is Postgres. The hosted copy and this Mac use the builder's Neon project `replate`: the `main` branch for production, a `dev` branch for local work. Drizzle talks to Neon through `pg`. Tests, CI, and a clone with no Neon URL run the same schema on `@electric-sql/pglite`, an in-process Postgres, so no test needs a network or a secret.

People sign in with a username and password. Passwords are hashed with Node's `scrypt` and a random salt per password; the hash lives in `users.password_hash`. Google sign-in is removed. The passwordless local button stays, only on `http://localhost:3000`.

Migrations run before the server starts (`predev`, `start`, the container command), not when a module loads. `next build` never opens the database.

## Why

The builder asked for Neon and for plain username and password accounts. A Postgres database outlives a container, so the Railway volume now only holds images.

## Consequence

- Free refills are open to every signed-in user while `EDITOR_PROVIDER=local`, because an edit then costs nothing. A paid editor needs Stripe for more credits.
- Failed sign-ins are capped at 10 per username per 15 minutes, counted in memory. That is right for one container; a second instance needs the count in the database.
- There is no password reset and no email. A forgotten password means a new account.
- Old SQLite data does not carry over.
