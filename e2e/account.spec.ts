import { expect, test } from "@playwright/test";

// A test account on this run's private database; the password is a fixture, not a secret.
const USERNAME = "e2e.user";
const PASSWORD = "fixture-password-1";

async function fill(page: import("@playwright/test").Page, password: string) {
	await page.getByLabel("Username").fill(USERNAME);
	await page.getByLabel("Password").fill(password);
}

test("create an account, sign out, refuse a wrong password, sign back in", async ({ page }) => {
	await page.goto("/");
	await fill(page, PASSWORD);
	await page.getByRole("button", { name: "Create account" }).click();
	await expect(page.getByTestId("balance")).toHaveText("10");
	await expect(page.getByText(USERNAME)).toBeVisible();

	await page.getByRole("button", { name: "Sign out" }).click();
	await fill(page, "not-the-password");
	await page.getByRole("button", { name: "Sign in" }).click();
	await expect(page.getByText("Wrong username or password.")).toBeVisible();

	await fill(page, PASSWORD);
	await page.getByRole("button", { name: "Create account" }).click();
	await expect(page.getByText("That username is taken.")).toBeVisible();

	await fill(page, PASSWORD);
	await page.getByRole("button", { name: "Sign in" }).click();
	await expect(page.getByTestId("balance")).toHaveText("10");
});
