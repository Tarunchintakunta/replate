import { eq } from "drizzle-orm";
import { migrate } from "drizzle-orm/better-sqlite3/migrator";
import { v4 as uuidv4 } from "uuid";
import { afterAll, beforeAll, describe, expect, it } from "vitest";
import { db, sqlite } from "../../db/client";
import { images, users } from "../../db/schema";
import { generationKey, originalKey, readPng, writePng } from "./store";

const TRANSPARENT_PIXEL = Buffer.from(
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
	"base64",
);

describe("storage", () => {
	beforeAll(() => {
		// Run migrations on the temp db
		migrate(db, { migrationsFolder: "db/migrations" });
	});

	afterAll(() => {
		sqlite.close();
	});

	it("rejects a key that contains ..", async () => {
		await expect(writePng("../foo.png", TRANSPARENT_PIXEL)).rejects.toThrow(
			"Path traversal detected",
		);
		await expect(readPng("../foo.png")).rejects.toThrow(
			"Path traversal detected",
		);
		await expect(
			writePng("originals/../../foo.png", TRANSPARENT_PIXEL),
		).rejects.toThrow("Path traversal detected");
	});

	it("writes and reads a PNG and round-trips a row", async () => {
		const userId = uuidv4();
		const imageId = uuidv4();

		// Insert user
		await db.insert(users).values({
			id: userId,
			email: "test@example.com",
			name: "Testy",
			createdAt: new Date(),
		});

		const key = originalKey(imageId);
		// also test generationKey mapping
		expect(generationKey(imageId)).toBe(`generations/${imageId}.png`);

		// Insert image
		await db.insert(images).values({
			id: imageId,
			userId,
			width: 1,
			height: 1,
			storageKey: key,
			createdAt: new Date(),
		});

		// Write PNG
		await writePng(key, TRANSPARENT_PIXEL);

		// Read PNG back
		const data = await readPng(key);
		expect(data.equals(TRANSPARENT_PIXEL)).toBe(true);

		// Read DB back
		const [imgRow] = await db
			.select()
			.from(images)
			.where(eq(images.id, imageId));
		expect(imgRow).toBeDefined();
		expect(imgRow?.storageKey).toBe(key);
	});
});
