import fs from "node:fs/promises";
import { expect, test } from "@playwright/test";
import sharp from "sharp";
import { signIn } from "./signin";

test("a failed replace shows one danger sentence and keeps the balance", async ({ page }, testInfo) => {
	const uploadPath = testInfo.outputPath("plain.png");
	await fs.writeFile(
		uploadPath,
		await sharp({ create: { width: 300, height: 150, channels: 4, background: "white" } })
			.png()
			.toBuffer(),
	);

	// The server honors this header only under NODE_ENV=test (see playwright.config.ts).
	await page.route("**/api/generations", (route) =>
		route.request().method() === "POST"
			? route.continue({ headers: { ...route.request().headers(), "x-replate-fail": "1" } })
			: route.continue(),
	);

	await signIn(page);
	await expect(page.getByTestId("balance")).toHaveText("10");
	await page.locator('input[type="file"]').setInputFiles(uploadPath);
	await expect(page.locator('img[alt="Uploaded"]')).toBeVisible();

	await page.getByRole("button", { name: "Detect Text" }).click();
	await page.getByLabel("Replacement").fill("HELLO");
	await page.getByRole("button", { name: "Replace text" }).click();

	const alert = page.getByRole("alert");
	await expect(alert).toHaveCount(1);
	await expect(alert).toContainText("The edit failed");
	await expect(page.locator('img[alt="Uploaded"]')).toBeVisible();
	await expect(page.getByTestId("balance")).toHaveText("10");

	await page.reload();
	await expect(page.getByTestId("balance")).toHaveText("10");
});
