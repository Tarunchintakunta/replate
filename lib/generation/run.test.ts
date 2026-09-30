import fs from "node:fs";
import path from "node:path";
import sharp from "sharp";
import { v4 as uuidv4 } from "uuid";
import { describe, expect, it, vi } from "vitest";
import { db } from "../../db/client";
import { generations, images, users } from "../../db/schema";
import { balanceOf, grantTrial } from "../credits/ledger";
import { MockEditor } from "../editor/mock";
import type { ImageEditor } from "../editor/types";
import { originalKey, writePng } from "../images/store";
import { type GenerationRequest, runGeneration } from "./run";

async function setup(opts: { trial?: boolean } = {}) {
	const userId = uuidv4();
	db.transaction((tx) => {
		tx.insert(users)
			.values({ id: userId, email: `${userId}@example.com`, name: "T", createdAt: new Date() })
			.run();
		if (opts.trial !== false) grantTrial(userId, tx);
	});
	const imageId = uuidv4();
	const png = await sharp({
		create: { width: 200, height: 100, channels: 4, background: "white" },
	})
		.png()
		.toBuffer();
	await writePng(originalKey(imageId), png);
	db.insert(images)
		.values({
			id: imageId,
			userId,
			width: 200,
			height: 100,
			storageKey: originalKey(imageId),
			createdAt: new Date(),
		})
		.run();
	const body: GenerationRequest = {
		imageId,
		lines: [
			{ lineId: null, from: "SALE", to: "HELLO", box: { x: 8, y: 8, width: 48, height: 16 } },
		],
	};
	return { userId, body };
}

const outputPath = (generationId: string) =>
	path.resolve(process.env.STORAGE_PATH as string, "generations", `${generationId}.png`);

class ThrowingEditor implements ImageEditor {
	async edit(): Promise<never> {
		throw new Error("provider exploded");
	}
}

describe("runGeneration", () => {
	it("stores the PNG and moves the balance from 10 to 0", async () => {
		const { userId, body } = await setup();
		const result = await runGeneration(userId, body, new MockEditor(), "mock");

		expect(result.status).toBe(200);
		if (result.status !== 200) return;
		expect(fs.existsSync(outputPath(result.generationId))).toBe(true);
		expect(balanceOf(userId)).toBe(0);
	});

	it("leaves the balance at 10 and writes a failed row when the editor throws", async () => {
		const { userId, body } = await setup();
		const result = await runGeneration(userId, body, new ThrowingEditor(), "mock");

		expect(result.status).toBe(502);
		expect(balanceOf(userId)).toBe(10);
		const rows = db.select().from(generations).all().filter((g) => g.userId === userId);
		expect(rows).toHaveLength(1);
		expect(rows[0].status).toBe("failed");
		expect(rows[0].error).toContain("provider exploded");
		expect(fs.existsSync(outputPath(rows[0].id))).toBe(false);
	});

	it("never calls edit at balance 0", async () => {
		const { userId, body } = await setup({ trial: false });
		const editor = new MockEditor();
		const spy = vi.spyOn(editor, "edit");

		const result = await runGeneration(userId, body, editor, "mock");
		expect(result.status).toBe(402);
		expect(spy).not.toHaveBeenCalled();
	});

	it("returns 429 on the 11th attempt in an hour without calling edit", async () => {
		const { userId, body } = await setup();
		for (let i = 0; i < 10; i++) {
			await runGeneration(userId, body, new ThrowingEditor(), "mock");
		}
		const editor = new MockEditor();
		const spy = vi.spyOn(editor, "edit");

		const result = await runGeneration(userId, body, editor, "mock");
		expect(result.status).toBe(429);
		expect(spy).not.toHaveBeenCalled();
		expect(balanceOf(userId)).toBe(10);
	});

	it("returns 404 for another user's image", async () => {
		const { body } = await setup();
		const other = await setup();
		const result = await runGeneration(other.userId, body, new MockEditor(), "mock");
		expect(result.status).toBe(404);
	});

	it("returns 409 while a request for the same user is in flight", async () => {
		const { userId, body } = await setup();
		// runGeneration takes the lock synchronously, before its first await.
		const first = runGeneration(userId, body, new MockEditor(), "mock");
		const second = await runGeneration(userId, body, new MockEditor(), "mock");
		expect(second.status).toBe(409);
		expect((await first).status).toBe(200);
	});
});
