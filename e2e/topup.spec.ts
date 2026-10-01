import { expect, test } from "@playwright/test";
import { signIn } from "./signin";

test("the local user adds 100 credits from the pricing page", async ({ page }) => {
	await signIn(page);
	// The pill shows "…" until the balance loads.
	await expect(page.getByTestId("balance")).toHaveText(/^\d+$/);
	const before = Number(await page.getByTestId("balance").textContent());

	await page.getByRole("link", { name: "Credits" }).click();
	await page.getByRole("button", { name: "Add 100 local credits" }).click();

	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByTestId("balance")).toHaveText(String(before + 100));
});
