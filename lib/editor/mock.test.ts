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
