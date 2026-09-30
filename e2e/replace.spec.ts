import fs from "node:fs/promises";
import { expect, test } from "@playwright/test";
import sharp from "sharp";

test("replace SALE with HELLO, download, and spend 10 credits", async ({ page }, testInfo) => {
	const upload = await sharp({
		create: { width: 400, height: 200, channels: 4, background: "white" },
	})
		.composite([
			{
				input: Buffer.from(
					'<svg width="400" height="200"><text x="10" y="22" font-size="16" font-family="sans-serif">SALE</text></svg>',
				),
			},
		])
		.png()
		.toBuffer();
	const uploadPath = testInfo.outputPath("sale.png");
	await fs.writeFile(uploadPath, upload);

	await page.goto("/");
	await expect(page.getByTestId("balance")).toHaveText("10");

	await page.locator('input[type="file"]').setInputFiles(uploadPath);
	await expect(page.locator('img[alt="Uploaded"]')).toBeVisible();

	await page.getByRole("button", { name: "Detect Text" }).click();
	await expect(page.getByText('"SALE"')).toBeVisible();
	await page.getByLabel("Replacement").fill("HELLO");

	await expect(page.getByText("Font and background matching is best-effort.")).toBeVisible();
	await page.getByRole("button", { name: "Replace text" }).click();

	await expect(page.locator('img[alt="Result"]')).toBeVisible();
	const downloadPromise = page.waitForEvent("download");
	await page.getByRole("link", { name: "Download PNG" }).click();
	const download = await downloadPromise;
	const downloaded = await fs.readFile(await download.path());

	expect(downloaded.subarray(1, 4).toString()).toBe("PNG");
	expect(downloaded.equals(upload)).toBe(false);

	await expect(page.getByTestId("balance")).toHaveText("0");
	await expect(page.getByRole("button", { name: /succeeded/ })).toBeVisible();

	await page.reload();
	await expect(page.getByTestId("balance")).toHaveText("0");
});
