import { v4 as uuidv4 } from "uuid";
import { describe, expect, it } from "vitest";
import { db } from "../../db/client";
import { generations, images, users } from "../../db/schema";
import { balanceOf, debitGeneration, grantLocalPack, grantTrial } from "./ledger";

async function newUser(): Promise<string> {
	const id = uuidv4();
	await db.insert(users).values({ id, email: `${id}@example.com`, name: "Test", createdAt: new Date() });
	return id;
}

// credit_ledger.generation_id is a foreign key, so debits need a real row.
async function newGeneration(userId: string): Promise<string> {
	const imageId = uuidv4();
	await db.insert(images).values({
			id: imageId,
			userId,
			width: 1,
			height: 1,
			storageKey: "x",
			createdAt: new Date(),
		});
	const id = uuidv4();
	await db.insert(generations).values({
			id,
			userId,
			imageId,
			provider: "mock",
			model: "mock",
			status: "failed",
			createdAt: new Date(),
		});
	return id;
}

describe("ledger", () => {
	it("grants trial to a new user exactly once", async () => {
		const userId = await newUser();
		await db.transaction((tx) => grantTrial(userId, tx));
		expect(await balanceOf(userId)).toBe(10);

		await db.transaction((tx) => grantTrial(userId, tx));
		expect(await balanceOf(userId)).toBe(10);
	});

	it("debits to zero, then throws without writing", async () => {
		const userId = await newUser();
		await db.transaction((tx) => grantTrial(userId, tx));

		const genOne = await newGeneration(userId);
		await db.transaction((tx) => debitGeneration(userId, genOne, tx));
		expect(await balanceOf(userId)).toBe(0);

		const genId = await newGeneration(userId);
		await expect(
			db.transaction((tx) => debitGeneration(userId, genId, tx)),
		).rejects.toThrow("InsufficientCredits");
		expect(await balanceOf(userId)).toBe(0);
	});

	it("leaves the sum unchanged if a transaction rolls back", async () => {
		const userId = await newUser();
		await db.transaction((tx) => grantTrial(userId, tx));
		const genId = await newGeneration(userId);

		await expect(
			db.transaction(async (tx) => {
				await debitGeneration(userId, genId, tx);
				throw new Error("Force rollback");
			}),
		).rejects.toThrow("Force rollback");
		expect(await balanceOf(userId)).toBe(10);
	});

	it("adds a local pack of 100 on top of the balance, every time it is asked", async () => {
		const userId = await newUser();
		await db.transaction((tx) => grantTrial(userId, tx));
		await db.transaction((tx) => grantLocalPack(userId, tx));
		await db.transaction((tx) => grantLocalPack(userId, tx));
		expect(await balanceOf(userId)).toBe(210);
	});
});
