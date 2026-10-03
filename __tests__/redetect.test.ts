import sharp from "sharp";
import { v4 as uuidv4 } from "uuid";
import { afterEach, expect, it, vi } from "vitest";
import { db } from "../db/client";
import { images } from "../db/schema";
import { ensureUser } from "../lib/auth/users";
import { originalKey, writePng } from "../lib/images/store";

const session = vi.hoisted(() => ({ user: null as null | { id: string } }));
vi.mock("../lib/auth/current-user", () => ({
	currentUser: async () => session.user,
}));

const { POST: detect } = await import("../src/app/api/images/[id]/ocr/route");
const { POST: replace } = await import("../src/app/api/generations/route");

afterEach(() => vi.unstubAllEnvs());

// A replacement keeps a link to the OCR line it changed. Reading the picture again
// replaces those lines, and must not fail because a past result points at one.
it("detects again on an image that already has a result", async () => {
	vi.stubEnv("OCR_MODE", "fixture");
	vi.stubEnv("EDITOR_PROVIDER", "mock");
	const user = await ensureUser(`${uuidv4()}@example.com`, "T");
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
	await db.insert(images).values({
		id: imageId,
		userId: user.id,
		width: 100,
		height: 50,
		storageKey: originalKey(imageId),
		createdAt: new Date(),
	});
	const params = { params: Promise.resolve({ id: imageId }) };
	const req = () => new Request("http://localhost/x", { method: "POST" });

	const first = await (await detect(req(), params)).json();
	const [line] = first.lines;
	const made = await replace(
		new Request("http://localhost/api/generations", {
			method: "POST",
			body: JSON.stringify({
				imageId,
				lines: [{ lineId: line.id, from: line.text, to: "HELLO", box: line }],
			}),
		}),
	);
	expect(made.status).toBe(200);

	const again = await detect(req(), params);
	expect(again.status).toBe(200);
	expect((await again.json()).lines).toHaveLength(1);
});
