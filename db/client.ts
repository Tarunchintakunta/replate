import { drizzle } from 'drizzle-orm/better-sqlite3';
import Database from 'better-sqlite3';

const dbPath = process.env.DATABASE_URL || 'data/replate.db';

export const sqlite = new Database(dbPath);
sqlite.pragma('journal_mode = WAL');

// Turn on foreign keys
sqlite.pragma('foreign_keys = ON');

export const db = drizzle(sqlite);
