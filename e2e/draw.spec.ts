import fs from "node:fs/promises";
import { expect, test } from "@playwright/test";
import sharp from "sharp";
import { signIn } from "./signin";

const cases = [
	{ name: "tall", width: 700, height: 1400 },
	{ name: "wide", width: 1400, height: 500 },
];

for (const c of cases) {
	test(`a drawn box on a ${c.name} image records image-pixel coords`, async ({
		page,
	}) => {
		const png = await sharp({
			create: {
				width: c.width,
				height: c.height,
				channels: 3,
				background: { r: 240, g: 240, b: 240 },
			},
		})
			.png()
			.toBuffer();
		await fs.mkdir("temp", { recursive: true });
		const filePath = `temp/draw-${c.name}.png`;
		await fs.writeFile(filePath, png);

		await signIn(page);
		await page.locator('input[type="file"]').setInputFiles(filePath);
		const img = page.locator('img[alt="Uploaded"]');
		await expect(img).toBeVisible();

		await expect
			.poll(() => img.evaluate((el: HTMLImageElement) => el.naturalWidth))
			.toBe(c.width);

		const box = await img.boundingBox();
		if (!box) throw new Error("image has no bounding box");
		// The image fits the viewport and is not letterboxed inside its frame.
		const viewport = page.viewportSize();
		expect(box.height).toBeLessThanOrEqual(viewport?.height ?? 0);
		expect(Math.abs(box.width / box.height - c.width / c.height)).toBeLessThan(
			0.02,
		);
		const at = (fx: number, fy: number) =>
			[box.x + box.width * fx, box.y + box.height * fy] as const;

		await page.mouse.move(...at(0.25, 0.4));
		await page.mouse.down();
		await page.mouse.move(...at(0.45, 0.5), { steps: 5 });
		await page.mouse.move(...at(0.6, 0.55), { steps: 5 });
		await page.mouse.up();

		const label = page.getByText(/^Box at x:\d+ y:\d+$/).first();
		await expect(label).toBeVisible();
		const [, x, y] = ((await label.textContent()) ?? "")
			.match(/x:(\d+) y:(\d+)/)
			?.map(Number) ?? [0, Number.NaN, Number.NaN];
		expect(Math.abs(x - c.width * 0.25)).toBeLessThanOrEqual(4);
		expect(Math.abs(y - c.height * 0.4)).toBeLessThanOrEqual(4);
	});
}
