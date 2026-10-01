import { existsSync } from "node:fs";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import sharp from "sharp";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LocalEditor } from "./local";

const PAPER = { r: 243, g: 239, b: 230 };
const W = 600;
const H = 300;
// "SALE" drawn at 72px from (60, 170) fits inside this box with room to spare.
const BOX = { x: 50, y: 100, width: 240, height: 90 };

const fixture = () =>
	sharp({ create: { width: W, height: H, channels: 3, background: PAPER } })
		.composite([
			{
				input: Buffer.from(
					`<svg width="${W}" height="${H}"><text x="60" y="170" font-size="72" font-family="sans-serif" fill="#1c1915">SALE</text></svg>`,
				),
			},
		])
		.png()
		.toBuffer();

async function pixels(png: Buffer) {
	const { data, info } = await sharp(png).removeAlpha().raw().toBuffer({ resolveWithObject: true });
	return { data, info };
}

/** Largest channel difference between two images over pixels where `where(x, y)` holds. */
function maxDiff(a: Buffer, b: Buffer, where: (x: number, y: number) => boolean): number {
	let worst = 0;
	for (let y = 0; y < H; y++) {
		for (let x = 0; x < W; x++) {
			if (!where(x, y)) continue;
			for (let c = 0; c < 3; c++) {
				const i = (y * W + x) * 3 + c;
				worst = Math.max(worst, Math.abs(a[i] - b[i]));
			}
		}
	}
	return worst;
}

// The glyphs may reach a few pixels past the box; the margin keeps the checks honest.
const nearBox = (x: number, y: number) =>
	x >= BOX.x - 40 && x < BOX.x + BOX.width + 200 && y >= BOX.y - 40 && y < BOX.y + BOX.height + 40;

afterEach(() => {
	vi.restoreAllMocks();
});

describe("LocalEditor", () => {
	it("explains how to install when the venv is missing", async () => {
		const dir = await fs.mkdtemp(path.join(os.tmpdir(), "replate-noedit-"));
		vi.spyOn(process, "cwd").mockReturnValue(dir);
		try {
			await expect(
				new LocalEditor().edit({ imageBuffer: Buffer.alloc(0), replacements: [] }),
			).rejects.toThrow("The local editor is not installed. Run: python3 -m venv services/ocr/.venv");
		} finally {
			await fs.rm(dir, { recursive: true, force: true });
		}
	});
});

describe.skipIf(!existsSync("services/ocr/.venv/bin/python"))("LocalEditor sidecar", () => {
	it("redraws the box and leaves every other pixel alone", async () => {
		const original = await fixture();
		const result = await new LocalEditor().edit({
			imageBuffer: original,
			replacements: [{ from: "SALE", to: "HELLO", ...BOX }],
		});

		expect(result.provider).toBe("local");
		const before = await pixels(original);
		const after = await pixels(result.buffer);
		expect([after.info.width, after.info.height]).toEqual([W, H]);

		expect(maxDiff(before.data, after.data, (x, y) => !nearBox(x, y))).toBe(0);
		expect(maxDiff(before.data, after.data, nearBox)).toBeGreaterThan(100);
		// New words are in the old ink color: some pixel near the box is still that dark.
		let darkest = 255;
		for (let i = 0; i < after.data.length; i += 3) darkest = Math.min(darkest, after.data[i]);
		expect(darkest).toBeLessThan(60);
	}, 30000);

	it("removes the words and rebuilds the background for an empty replacement", async () => {
		const original = await fixture();
		const blank = await sharp({ create: { width: W, height: H, channels: 3, background: PAPER } })
			.png()
			.toBuffer();
		const result = await new LocalEditor().edit({
			imageBuffer: original,
			replacements: [{ from: "SALE", to: "", ...BOX }],
		});

		const after = await pixels(result.buffer);
		const paper = await pixels(blank);
		expect(maxDiff(after.data, paper.data, () => true)).toBeLessThanOrEqual(3);
	}, 30000);

	it("draws into a flat box that has no old words to match", async () => {
		const blank = await sharp({ create: { width: W, height: H, channels: 3, background: PAPER } })
			.png()
			.toBuffer();
		const result = await new LocalEditor().edit({
			imageBuffer: blank,
			replacements: [{ from: "", to: "NEW", ...BOX }],
		});

		const before = await pixels(blank);
		const after = await pixels(result.buffer);
		expect(maxDiff(before.data, after.data, nearBox)).toBeGreaterThan(100);
		expect(maxDiff(before.data, after.data, (x, y) => !nearBox(x, y))).toBe(0);
	}, 30000);
});
