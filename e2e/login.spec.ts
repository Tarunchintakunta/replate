import { expect, test } from "@playwright/test";

test("the landing page leads to sign-in, the desk needs a session, and sign out returns home", async ({ page, request }) => {
	await page.goto("/");
	await expect(page.getByRole("heading", { name: /Change the words/ })).toBeVisible();
	expect((await request.get("/api/credits")).status()).toBe(401);

	await page.goto("/dashboard");
	await expect(page).toHaveURL(/\/signin$/);

	await page.getByRole("button", { name: "Continue as local" }).click();
	await expect(page).toHaveURL(/\/dashboard$/);
	await expect(page.getByTestId("balance")).toHaveText("10");
	await expect(page.getByText("local@replate.test")).toBeVisible();

	await page.goto("/signin");
	await expect(page).toHaveURL(/\/dashboard$/);

	await page.getByRole("button", { name: "Sign out" }).click();
	await expect(page).toHaveURL(/\/$/);
	await expect(page.getByRole("navigation").getByRole("link", { name: "Sign in" })).toBeVisible();
});
