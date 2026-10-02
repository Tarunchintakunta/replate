import path from "node:path";
import { PGlite } from "@electric-sql/pglite";
import { drizzle as pgliteDrizzle } from "drizzle-orm/pglite";
import { migrate as pgliteMigrate } from "drizzle-orm/pglite/migrator";
import { drizzle, type NodePgDatabase } from "drizzle-orm/node-postgres";
import { migrate as pgMigrate } from "drizzle-orm/node-postgres/migrator";
import { Pool } from "pg";
import * as schema from "./schema";

// A postgres:// URL (Neon) is the real database. Without one, an in-process Postgres
// stands in: in memory for tests, or in the folder DATABASE_URL names.
type Db = NodePgDatabase<typeof schema>;

const migrationsFolder = path.resolve("db/migrations");

function open(): { db: Db; migrate: () => Promise<void> } {
	const url = process.env.DATABASE_URL || "";
	if (/^postgres(ql)?:\/\//.test(url)) {
		const db = drizzle(new Pool({ connectionString: url, max: 5 }), { schema });
		return { db, migrate: () => pgMigrate(db, { migrationsFolder }) };
	}
	// An empty in-memory database outside tests would lose every account on restart.
	if (!url && process.env.NODE_ENV !== "test") {
		throw new Error("DATABASE_URL is not set. Use a postgres:// URL, or a folder for a local database.");
	}
	const local = pgliteDrizzle(new PGlite(url || undefined), { schema });
	return {
		// Same query builder and the same results; only the driver differs.
		db: local as unknown as Db,
		migrate: () => pgliteMigrate(local, { migrationsFolder }),
	};
}

// Opened on first use. `next build` imports this from every worker, and none of them
// should hold a connection or a database folder open. Kept on globalThis because Next
// loads this module once per bundle (pages, API routes), and two in-process Postgres
// instances on one folder lock each other out.
const shared = globalThis as { replateDb?: ReturnType<typeof open> };
const handle = () => {
	shared.replateDb ??= open();
	return shared.replateDb;
};

export const db = new Proxy({} as Db, {
	get: (_, key) => Reflect.get(handle().db, key),
});

/** Brings the schema up to date. Run once before the server starts, and in test setup. */
export function migrate(): Promise<void> {
	return handle().migrate();
}
