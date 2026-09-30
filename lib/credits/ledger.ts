import { and, eq, sum } from "drizzle-orm";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../db/client";
import { creditLedger } from "../../db/schema";

// better-sqlite3 transactions are synchronous: an async callback throws
// "Transaction function cannot return a promise". Callers pass the tx from
// `db.transaction((tx) => { ... })` and these helpers run sync inside it.
export type Tx = Parameters<Parameters<typeof db.transaction>[0]>[0];

export const GENERATION_COST = 10;
const TRIAL_GRANT = 10;
export const PACK_CREDITS = 100;

export function balanceOf(userId: string, tx: Tx | typeof db = db): number {
	const row = tx
		.select({ value: sum(creditLedger.delta) })
		.from(creditLedger)
		.where(eq(creditLedger.userId, userId))
		.get();
	return Number(row?.value) || 0;
}

export function grantTrial(userId: string, tx: Tx): void {
	const existing = tx
		.select({ id: creditLedger.id })
		.from(creditLedger)
		.where(and(eq(creditLedger.userId, userId), eq(creditLedger.reason, "trial")))
		.get();
	if (existing) return;

	tx.insert(creditLedger)
		.values({
			id: uuidv4(),
			userId,
			delta: TRIAL_GRANT,
			reason: "trial",
			createdAt: new Date(),
		})
		.run();
}

export function debitGeneration(
	userId: string,
	generationId: string,
	tx: Tx,
): void {
	if (balanceOf(userId, tx) < GENERATION_COST) {
		throw new Error("InsufficientCredits");
	}

	tx.insert(creditLedger)
		.values({
			id: uuidv4(),
			userId,
			delta: -GENERATION_COST,
			reason: "debit_generation",
			generationId,
			createdAt: new Date(),
		})
		.run();
}

export function creditPack(userId: string, stripeEventId: string, tx: Tx): void {
	tx.insert(creditLedger)
		.values({
			id: uuidv4(),
			userId,
			delta: PACK_CREDITS,
			reason: "stripe_pack",
			stripeEventId,
			createdAt: new Date(),
		})
		.run();
}
