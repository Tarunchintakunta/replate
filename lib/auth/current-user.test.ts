import { and, eq } from "drizzle-orm";
import { afterEach, describe, expect, it, vi } from "vitest";
import { db } from "../../db/client";
import { creditLedger, users } from "../../db/schema";
import { balanceOf } from "../credits/ledger";
import {
	ensureUser,
	hashPassword,
	LOCAL_EMAIL,
	localCreditsAllowed,
	localLoginAllowed,
	login,
	register,
	verifyPassword,
} from "./users";

describe("ensureUser", () => {
	it("creates local@replate.test once and grants the trial once", async () => {
		const first = await ensureUser(LOCAL_EMAIL, "Local Dev");
		const second = await ensureUser(LOCAL_EMAIL, "Local Dev");

		expect(second.id).toBe(first.id);
		expect(await db.select().from(users).where(eq(users.email, LOCAL_EMAIL))).toHaveLength(1);
		const trials = await db
			.select()
			.from(creditLedger)
			.where(and(eq(creditLedger.userId, first.id), eq(creditLedger.reason, "trial")));
		expect(trials).toHaveLength(1);
		expect(await balanceOf(first.id)).toBe(10);
	});
});

describe("passwords", () => {
	it("verify only the password they were made from, with a fresh salt each time", async () => {
		const a = await hashPassword("correct horse");
		const b = await hashPassword("correct horse");
		expect(a).not.toBe(b);
		expect(await verifyPassword("correct horse", a)).toBe(true);
		expect(await verifyPassword("correct hors", a)).toBe(false);
		expect(await verifyPassword("correct horse", "not-a-hash")).toBe(false);
	});
});

describe("register and login", () => {
	it("creates an account with the trial and signs it in, case-insensitively", async () => {
		const made = await register("  Ana.Lee ", "long enough");
		expect("id" in made).toBe(true);
		if (!("id" in made)) return;
		expect(await balanceOf(made.id)).toBe(10);

		expect(await login("ana.lee", "long enough")).toEqual({ id: made.id, name: "ana.lee" });
		expect(await login("ANA.LEE", "long enough")).toEqual({ id: made.id, name: "ana.lee" });
	});

	it("refuses a wrong password, an unknown name, and a taken name", async () => {
		await register("bob", "password1");
		expect(await login("bob", "password2")).toBeNull();
		expect(await login("nobody", "password1")).toBeNull();
		expect(await register("BOB", "another one")).toEqual({ error: "That username is taken." });
	});

	it("refuses a bad username or a short password and stores nothing", async () => {
		expect(await register("a b", "long enough")).toHaveProperty("error");
		expect(await register("bo", "long enough")).toHaveProperty("error");
		expect(await register("carol", "short")).toHaveProperty("error");
		expect(await db.select().from(users).where(eq(users.username, "carol"))).toHaveLength(0);
	});

	it("never stores the password itself", async () => {
		await register("dave", "plain text pw");
		const [row] = await db.select().from(users).where(eq(users.username, "dave"));
		expect(row.passwordHash).toMatch(/^scrypt\$/);
		expect(row.passwordHash).not.toContain("plain text pw");
	});
});

describe("localLoginAllowed", () => {
	afterEach(() => vi.unstubAllEnvs());

	it("is true only for exactly http://localhost:3000", () => {
		vi.stubEnv("APP_URL", "http://localhost:3000");
		expect(localLoginAllowed()).toBe(true);
		for (const url of ["https://replate.example", "http://localhost:3001", "http://127.0.0.1:3000"]) {
			vi.stubEnv("APP_URL", url);
			expect(localLoginAllowed()).toBe(false);
		}
	});
});

describe("localCreditsAllowed", () => {
	afterEach(() => vi.unstubAllEnvs());

	it("is true only for the local user on http://localhost:3000", () => {
		vi.stubEnv("APP_URL", "http://localhost:3000");
		expect(localCreditsAllowed(LOCAL_EMAIL)).toBe(true);
		expect(localCreditsAllowed("someone@example.com")).toBe(false);
		expect(localCreditsAllowed(null)).toBe(false);

		vi.stubEnv("APP_URL", "https://replate.example");
		expect(localCreditsAllowed(LOCAL_EMAIL)).toBe(false);
	});
});
