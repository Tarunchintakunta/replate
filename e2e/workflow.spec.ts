import fs from "node:fs/promises";
import { expect, test } from "@playwright/test";
import sharp from "sharp";
import { signIn } from "./signin";

// Runs after topup.spec.ts (file order), so the shared local user has credits.
test("upload detects by itself, the result toggles, and a past result opens on its own picture", async ({
	page,
}, testInfo) => {
	const png = (width: number, height: number) =>
		sharp({ create: { width, height, channels: 3, background: "white" } })
			.png()
			.toBuffer();
	const widePath = testInfo.outputPath("wide.png");
	const tallPath = testInfo.outputPath("tall.png");
	await fs.writeFile(widePath, await png(400, 200));
	await fs.writeFile(tallPath, await png(200, 400));

	await signIn(page);
	await page.locator('input[type="file"]').setInputFiles(widePath);

	// No click on Detect Text: the upload starts it.
	await expect(page.getByText('"SALE"')).toBeVisible();
	await expect(page.getByText("0 of 1 chosen")).toBeVisible();
	await page.getByLabel("Replacement").fill("HELLO");
	await expect(page.getByText("1 of 1 chosen")).toBeVisible();
	await page.getByRole("button", { name: "Replace text" }).click();
	await expect(page.locator('img[alt="Result"]')).toBeVisible();

	await page.getByRole("button", { name: "Show original" }).click();
	await expect(page.locator('img[alt="Uploaded"]')).toBeVisible();
	await page.getByRole("button", { name: "Show result" }).click();
	await expect(page.locator('img[alt="Result"]')).toBeVisible();

	// A second picture replaces the first without a reload.
	await page.locator('input[type="file"]').setInputFiles(tallPath);
	const shown = page.locator('img[alt="Uploaded"]');
	await expect
		.poll(() => shown.evaluate((el: HTMLImageElement) => el.naturalWidth))
		.toBe(200);

	// The newest past result belongs to the wide picture and brings it back.
	await page.getByRole("button", { name: /succeeded/ }).first().click();
	const result = page.locator('img[alt="Result"]');
	await expect(result).toBeVisible();
	await expect
		.poll(() => result.evaluate((el: HTMLImageElement) => el.naturalWidth))
		.toBe(400);
	const box = await result.boundingBox();
	expect(Math.abs((box?.width ?? 0) / (box?.height ?? 1) - 2)).toBeLessThan(0.05);
});
