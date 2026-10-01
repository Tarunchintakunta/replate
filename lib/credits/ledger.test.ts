import { migrate } from "drizzle-orm/better-sqlite3/migrator";
import { v4 as uuidv4 } from "uuid";
import { beforeAll, describe, expect, it } from "vitest";
import { db } from "../../db/client";
import { generations, images, users } from "../../db/schema";
import { balanceOf, debitGeneration, grantLocalPack, grantTrial } from "./ledger";

function newUser(): string {
	const id = uuidv4();
	db.insert(users)
		.values({ id, email: `${id}@example.com`, name: "Test", createdAt: new Date() })
		.run();
	return id;
}

// credit_ledger.generation_id is a foreign key, so debits need a real row.
function newGeneration(userId: string): string {
	const imageId = uuidv4();
	db.insert(images)
		.values({
			id: imageId,
			userId,
			width: 1,
			height: 1,
			storageKey: "x",
			createdAt: new Date(),
		})
		.run();
	const id = uuidv4();
	db.insert(generations)
		.values({
			id,
			userId,
			imageId,
			provider: "mock",
			model: "mock",
			status: "failed",
			createdAt: new Date(),
		})
		.run();
	return id;
}

describe("ledger", () => {
	beforeAll(() => {
		migrate(db, { migrationsFolder: "db/migrations" });
	});

	it("grants trial to a new user exactly once", () => {
		const userId = newUser();
		db.transaction((tx) => grantTrial(userId, tx));
		expect(balanceOf(userId)).toBe(10);

		db.transaction((tx) => grantTrial(userId, tx));
		expect(balanceOf(userId)).toBe(10);
	});

	it("debits to zero, then throws without writing", () => {
		const userId = newUser();
		db.transaction((tx) => grantTrial(userId, tx));

		db.transaction((tx) => debitGeneration(userId, newGeneration(userId), tx));
		expect(balanceOf(userId)).toBe(0);

		const genId = newGeneration(userId);
		expect(() =>
			db.transaction((tx) => debitGeneration(userId, genId, tx)),
		).toThrow("InsufficientCredits");
		expect(balanceOf(userId)).toBe(0);
	});

	it("leaves the sum unchanged if a transaction rolls back", () => {
		const userId = newUser();
		db.transaction((tx) => grantTrial(userId, tx));
		const genId = newGeneration(userId);

		expect(() =>
			db.transaction((tx) => {
				debitGeneration(userId, genId, tx);
				throw new Error("Force rollback");
			}),
		).toThrow("Force rollback");
		expect(balanceOf(userId)).toBe(10);
	});

	it("adds a local pack of 100 on top of the balance, every time it is asked", () => {
		const userId = newUser();
		db.transaction((tx) => grantTrial(userId, tx));
		db.transaction((tx) => grantLocalPack(userId, tx));
		db.transaction((tx) => grantLocalPack(userId, tx));
		expect(balanceOf(userId)).toBe(210);
	});
});
