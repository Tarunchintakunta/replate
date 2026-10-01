import { and, eq } from "drizzle-orm";
import { afterEach, describe, expect, it, vi } from "vitest";
import { db } from "../../db/client";
import { creditLedger, users } from "../../db/schema";
import { balanceOf } from "../credits/ledger";
import { ensureUser, LOCAL_EMAIL, localCreditsAllowed, localLoginAllowed } from "./users";

describe("ensureUser", () => {
	it("creates local@replate.test once and grants the trial once", () => {
		const first = ensureUser(LOCAL_EMAIL, "Local Dev");
		const second = ensureUser(LOCAL_EMAIL, "Local Dev");

		expect(second.id).toBe(first.id);
		expect(db.select().from(users).where(eq(users.email, LOCAL_EMAIL)).all()).toHaveLength(1);
		const trials = db
			.select()
			.from(creditLedger)
			.where(and(eq(creditLedger.userId, first.id), eq(creditLedger.reason, "trial")))
			.all();
		expect(trials).toHaveLength(1);
		expect(balanceOf(first.id)).toBe(10);
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

		vi.stubEnv("APP_URL", "https://replate.example");
		expect(localCreditsAllowed(LOCAL_EMAIL)).toBe(false);
	});
});
