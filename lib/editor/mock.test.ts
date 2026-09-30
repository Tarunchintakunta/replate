import { describe, expect, it } from "vitest";
import sharp from "sharp";
import { MockEditor } from "./mock";

describe("MockEditor", () => {
	it("returns a different valid PNG for a normal replacement", async () => {
		const original = await sharp({
			create: {
				width: 400,
				height: 200,
				channels: 4,
				background: { r: 255, g: 255, b: 255, alpha: 1 },
			},
		})
			.png()
			.toBuffer();

		const editor = new MockEditor();
		const result = await editor.edit({
			imageBuffer: original,
			replacements: [
				{
					from: "sale",
					to: "discount",
					x: 10,
					y: 10,
					width: 100,
					height: 50,
				},
			],
		});

		expect(result.provider).toBe("mock");
		expect(result.model).toBe("mock");
		expect(result.buffer).toBeInstanceOf(Buffer);

		// Must differ from original
		expect(result.buffer.equals(original)).toBe(false);

		// Must be a valid PNG
		const metadata = await sharp(result.buffer).metadata();
		expect(metadata.format).toBe("png");
	});

	it("returns a different valid PNG for an empty replacement (removal)", async () => {
		const original = await sharp({
			create: {
				width: 400,
				height: 200,
				channels: 4,
				background: { r: 255, g: 255, b: 255, alpha: 1 },
			},
		})
			.png()
			.toBuffer();

		const editor = new MockEditor();
		const result = await editor.edit({
			imageBuffer: original,
			replacements: [
				{
					from: "sale",
					to: "",
					x: 10,
					y: 10,
					width: 100,
					height: 50,
				},
			],
		});

		expect(result.provider).toBe("mock");
		expect(result.model).toBe("mock");
		expect(result.buffer).toBeInstanceOf(Buffer);
		expect(result.buffer.equals(original)).toBe(false);

		const metadata = await sharp(result.buffer).metadata();
		expect(metadata.format).toBe("png");
	});
});

describe("MockEditor removal fill", () => {
	it("fills a removed box with the color just outside its top-left corner", async () => {
		const bg = { r: 30, g: 120, b: 200 };
		const original = await sharp({
			create: { width: 2000, height: 1000, channels: 3, background: bg },
		})
			.png()
			.toBuffer();

		const result = await new MockEditor().edit({
			imageBuffer: original,
			replacements: [
				{ from: "sale", to: "", x: 400, y: 200, width: 300, height: 100 },
			],
		});

		// 2000px long edge is scaled to 1024, so the box center lands at (280, 128).
		const { data, info } = await sharp(result.buffer)
			.raw()
			.toBuffer({ resolveWithObject: true });
		expect(info.width).toBe(1024);
		const i = (128 * info.width + 280) * info.channels;
		expect([data[i], data[i + 1], data[i + 2]]).toEqual([bg.r, bg.g, bg.b]);
	});
});
