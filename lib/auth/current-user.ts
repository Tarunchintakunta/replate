import { eq } from "drizzle-orm";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../db/client";
import { users } from "../../db/schema";
import { grantTrial } from "../credits/ledger";

const LOCAL_EMAIL = "local@replate.test";

// ponytail: single local user until auth lands in issue 11.
export async function currentUser() {
	return db.transaction((tx) => {
		const existing = tx.select().from(users).where(eq(users.email, LOCAL_EMAIL)).get();
		if (existing) return existing;

		const user = { id: uuidv4(), email: LOCAL_EMAIL, name: "Local Dev", createdAt: new Date() };
		tx.insert(users).values(user).run();
		grantTrial(user.id, tx);
		return user;
	});
}
