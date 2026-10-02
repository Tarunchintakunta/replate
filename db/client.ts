import fs from "node:fs";
import path from "node:path";
import Database from "better-sqlite3";
import { drizzle } from "drizzle-orm/better-sqlite3";
import { migrate } from "drizzle-orm/better-sqlite3/migrator";

// Accept both `data/replate.db` and the `file:./data/replate.db` form in .env.example.
const dbPath = (process.env.DATABASE_URL || "data/replate.db").replace(/^file:/, "");
fs.mkdirSync(path.dirname(path.resolve(dbPath)), { recursive: true });

export const sqlite = new Database(dbPath);
// Wait on a lock instead of failing at once: `next build` opens this file from many workers.
sqlite.pragma("busy_timeout = 10000");
sqlite.pragma("journal_mode = WAL");
sqlite.pragma("foreign_keys = ON");

export const db = drizzle(sqlite);

// Migrations are idempotent and synchronous, so a fresh clone works without a manual step.
// Parallel build workers race on a new file: the loser fails on a table the winner just
// made, and its second pass finds the winner's record and does nothing.
const migrationsFolder = path.resolve("db/migrations");
try {
	migrate(db, { migrationsFolder });
} catch {
	migrate(db, { migrationsFolder });
}
