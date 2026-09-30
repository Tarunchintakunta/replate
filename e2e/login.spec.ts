import { expect, test } from "@playwright/test";

test("the desk appears only after Continue as local, and sign out returns", async ({ page, request }) => {
	await page.goto("/");
	await expect(page.getByText("Drop a PNG, JPG, or WebP.")).toHaveCount(0);
	expect((await request.get("/api/credits")).status()).toBe(401);

	await page.getByRole("button", { name: "Continue as local" }).click();
	await expect(page.getByTestId("balance")).toHaveText("10");
	await expect(page.getByText("local@replate.test")).toBeVisible();

	await page.getByRole("button", { name: "Sign out" }).click();
	await expect(page.getByRole("button", { name: "Continue as local" })).toBeVisible();
});
