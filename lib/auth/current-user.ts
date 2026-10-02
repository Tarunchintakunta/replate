import "server-only";
import { eq } from "drizzle-orm";
import { auth } from "@/auth";
import { db } from "../../db/client";
import { users } from "../../db/schema";

/** The signed-in user's row, or null without a session. */
export async function currentUser() {
	const session = await auth();
	const id = session?.user?.id;
	if (!id) return null;
	const [user] = await db.select().from(users).where(eq(users.id, id));
	return user ?? null;
}
