import { expect, test } from "@playwright/test";
import { signIn } from "./signin";

test("pricing shows the plain pack and is off without test keys", async ({ page }) => {
	await signIn(page);
	await page.getByRole("link", { name: "Credits" }).click();

	await expect(page).toHaveURL(/\/pricing$/);
	await expect(page.getByText("100 credits")).toBeVisible();
	await expect(page.getByText("test price $5")).toBeVisible();
	await expect(page.getByRole("button", { name: "Buy 100 credits" })).toBeDisabled();
	await expect(page.getByText("Payments are off until test keys are set.")).toBeVisible();
});
