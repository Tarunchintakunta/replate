import { expect, type Page } from "@playwright/test";

export async function signIn(page: Page) {
	await page.goto("/signin");
	await page.getByRole("button", { name: "Continue as local" }).click();
	await expect(page.getByTestId("balance")).toBeVisible();
}
