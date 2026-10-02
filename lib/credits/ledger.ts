import { and, eq, sum } from "drizzle-orm";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../db/client";
import { creditLedger } from "../../db/schema";

// Callers pass the tx from `await db.transaction(async (tx) => { ... })`.
export type Tx = Parameters<Parameters<typeof db.transaction>[0]>[0];

export const GENERATION_COST = 10;
const TRIAL_GRANT = 10;
export const PACK_CREDITS = 100;

export async function balanceOf(userId: string, tx: Tx | typeof db = db): Promise<number> {
	const [row] = await tx
		.select({ value: sum(creditLedger.delta) })
		.from(creditLedger)
		.where(eq(creditLedger.userId, userId));
	return Number(row?.value) || 0;
}

export async function grantTrial(userId: string, tx: Tx): Promise<void> {
	const [existing] = await tx
		.select({ id: creditLedger.id })
		.from(creditLedger)
		.where(and(eq(creditLedger.userId, userId), eq(creditLedger.reason, "trial")));
	if (existing) return;

	await tx.insert(creditLedger).values({
		id: uuidv4(),
		userId,
		delta: TRIAL_GRANT,
		reason: "trial",
		createdAt: new Date(),
	});
}

export async function debitGeneration(
	userId: string,
	generationId: string,
	tx: Tx,
): Promise<void> {
	if ((await balanceOf(userId, tx)) < GENERATION_COST) {
		throw new Error("InsufficientCredits");
	}

	await tx.insert(creditLedger).values({
		id: uuidv4(),
		userId,
		delta: -GENERATION_COST,
		reason: "debit_generation",
		generationId,
		createdAt: new Date(),
	});
}

/** A pack with no payment. The route decides who may have one. */
export async function grantLocalPack(userId: string, tx: Tx): Promise<void> {
	await tx.insert(creditLedger).values({
		id: uuidv4(),
		userId,
		delta: PACK_CREDITS,
		reason: "adjust",
		createdAt: new Date(),
	});
}

export async function creditPack(userId: string, stripeEventId: string, tx: Tx): Promise<void> {
	await tx.insert(creditLedger).values({
		id: uuidv4(),
		userId,
		delta: PACK_CREDITS,
		reason: "stripe_pack",
		stripeEventId,
		createdAt: new Date(),
	});
}
