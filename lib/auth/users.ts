import { eq } from "drizzle-orm";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../db/client";
import { users } from "../../db/schema";
import { grantTrial } from "../credits/ledger";

export const LOCAL_EMAIL = "local@replate.test";

/** Find the user by email, or create them with the +10 trial in the same transaction. */
export function ensureUser(email: string, name: string) {
	return db.transaction((tx) => {
		const existing = tx.select().from(users).where(eq(users.email, email)).get();
		if (existing) return existing;

		const user = { id: uuidv4(), email, name, createdAt: new Date() };
		tx.insert(users).values(user).run();
		grantTrial(user.id, tx);
		return user;
	});
}

export function appUrl(): string {
	return process.env.APP_URL || "http://localhost:3000";
}

/** The passwordless local button exists only for exactly this origin. */
export function localLoginAllowed(): boolean {
	return appUrl() === "http://localhost:3000";
}
