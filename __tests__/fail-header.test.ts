import sharp from "sharp";
import { v4 as uuidv4 } from "uuid";
import { afterEach, describe, expect, it, vi } from "vitest";
import { db } from "../db/client";
import { images } from "../db/schema";
import { ensureUser } from "../lib/auth/users";
import { balanceOf } from "../lib/credits/ledger";
import { originalKey, writePng } from "../lib/images/store";

const session = vi.hoisted(() => ({ user: null as null | { id: string } }));
vi.mock("../lib/auth/current-user", () => ({
	currentUser: async () => session.user,
}));

const { POST } = await import("../src/app/api/generations/route");

async function request() {
	const user = ensureUser(`${uuidv4()}@example.com`, "T");
	session.user = user;
	const imageId = uuidv4();
	await writePng(
		originalKey(imageId),
		await sharp({
			create: { width: 100, height: 50, channels: 4, background: "white" },
		})
			.png()
			.toBuffer(),
	);
	db.insert(images)
		.values({
			id: imageId,
			userId: user.id,
			width: 100,
			height: 50,
			storageKey: originalKey(imageId),
			createdAt: new Date(),
		})
		.run();
	const req = new Request("http://localhost/api/generations", {
		method: "POST",
		headers: { "x-replate-fail": "1" },
		body: JSON.stringify({
			imageId,
			lines: [
				{
					lineId: null,
					from: "A",
					to: "B",
					box: { x: 1, y: 1, width: 20, height: 10 },
				},
			],
		}),
	});
	return { user, req };
}

afterEach(() => vi.unstubAllEnvs());

describe("x-replate-fail", () => {
	it("forces a 502 without charging when NODE_ENV is test", async () => {
		vi.stubEnv("NODE_ENV", "test");
		const { user, req } = await request();
		expect((await POST(req)).status).toBe(502);
		expect(balanceOf(user.id)).toBe(10);
	});

	it("is ignored in development", async () => {
		vi.stubEnv("NODE_ENV", "development");
		const { user, req } = await request();
		expect((await POST(req)).status).toBe(200);
		expect(balanceOf(user.id)).toBe(0);
	});
});
