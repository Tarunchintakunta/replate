import { v4 as uuidv4 } from "uuid";
import { beforeAll, describe, expect, it, vi } from "vitest";
import { db } from "../db/client";
import { generations, images } from "../db/schema";
import { ensureUser } from "../lib/auth/users";
import { generationKey, originalKey, writePng } from "../lib/images/store";

// Route handlers read the session through currentUser(); swap in whichever user a test needs.
const session = vi.hoisted(() => ({ user: null as null | { id: string } }));
vi.mock("../lib/auth/current-user", () => ({
	currentUser: async () => session.user,
}));

const { GET: creditsGet } = await import("../src/app/api/credits/route");
const { POST: imagesPost } = await import("../src/app/api/images/route");
const { GET: imageFileGet } = await import(
	"../src/app/api/images/[id]/file/route"
);
const { POST: ocrPost } = await import("../src/app/api/images/[id]/ocr/route");
const { GET: generationsGet, POST: generationsPost } = await import(
	"../src/app/api/generations/route"
);
const { GET: generationFileGet } = await import(
	"../src/app/api/generations/[id]/file/route"
);

const owner = await ensureUser(`${uuidv4()}@example.com`, "Owner");
const stranger = await ensureUser(`${uuidv4()}@example.com`, "Stranger");
const imageId = uuidv4();
const generationId = uuidv4();
const params = (id: string) => ({ params: Promise.resolve({ id }) });
const json = (body: unknown) =>
	new Request("http://localhost/api/generations", {
		method: "POST",
		body: JSON.stringify(body),
	});
const replaceBody = {
	imageId,
	lines: [
		{
			lineId: null,
			from: "A",
			to: "B",
			box: { x: 0, y: 0, width: 1, height: 1 },
		},
	],
};

beforeAll(async () => {
	await writePng(originalKey(imageId), Buffer.from("png"));
	await writePng(generationKey(generationId), Buffer.from("png"));
	await db.insert(images).values({
		id: imageId,
		userId: owner.id,
		width: 1,
		height: 1,
		storageKey: originalKey(imageId),
		createdAt: new Date(),
	});
	await db.insert(generations).values({
		id: generationId,
		userId: owner.id,
		imageId,
		provider: "mock",
		model: "mock",
		status: "succeeded",
		outputKey: generationKey(generationId),
		createdAt: new Date(),
	});
});

describe("routes without a session", () => {
	it("return 401", async () => {
		session.user = null;
		const req = new Request("http://localhost/x");
		expect((await creditsGet()).status).toBe(401);
		expect(
			(await imagesPost(new Request("http://localhost/x", { method: "POST" })))
				.status,
		).toBe(401);
		expect((await imageFileGet(req, params(imageId))).status).toBe(401);
		expect((await ocrPost(req, params(imageId))).status).toBe(401);
		expect((await generationsGet(req)).status).toBe(401);
		expect((await generationsPost(json(replaceBody))).status).toBe(401);
		expect((await generationFileGet(req, params(generationId))).status).toBe(
			401,
		);
	});
});

describe("another user's ids", () => {
	it("return 404 and never leak the owner's rows", async () => {
		session.user = stranger;
		const req = new Request("http://localhost/x");
		expect((await imageFileGet(req, params(imageId))).status).toBe(404);
		expect((await ocrPost(req, params(imageId))).status).toBe(404);
		expect((await generationFileGet(req, params(generationId))).status).toBe(
			404,
		);
		expect((await generationsPost(json(replaceBody))).status).toBe(404);
		const list = await (
			await generationsGet(new Request("http://localhost/api/generations"))
		).json();
		expect(list.generations).toEqual([]);
	});

	it("still serve the owner", async () => {
		session.user = owner;
		const req = new Request("http://localhost/x");
		expect((await imageFileGet(req, params(imageId))).status).toBe(200);
		expect((await generationFileGet(req, params(generationId))).status).toBe(
			200,
		);
	});
});
