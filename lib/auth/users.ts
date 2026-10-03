import crypto from "node:crypto";
import { promisify } from "node:util";
import { eq } from "drizzle-orm";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../db/client";
import { users } from "../../db/schema";
import { providerName } from "../editor";
import { grantTrial } from "../credits/ledger";

export const LOCAL_EMAIL = "local@replate.test";

/** Find the user by email, or create them with the +10 trial in the same transaction. */
export function ensureUser(email: string, name: string) {
	return db.transaction(async (tx) => {
		const [existing] = await tx.select().from(users).where(eq(users.email, email));
		if (existing) return existing;

		const user = { id: uuidv4(), email, name, createdAt: new Date() };
		await tx.insert(users).values(user);
		await grantTrial(user.id, tx);
		return user;
	});
}

// Lowercase letters, digits, dot, dash, underscore. Case-folded so "Ana" and "ana" are one account.
export const USERNAME = /^[a-z0-9._-]{3,32}$/;
export const PASSWORD_MIN = 8;
const PASSWORD_MAX = 128;

const scrypt = promisify(crypto.scrypt) as (
	password: string,
	salt: Buffer,
	keylen: number,
) => Promise<Buffer>;

/** `scrypt$<salt>$<hash>`, both base64. The salt is random per password. */
export async function hashPassword(password: string): Promise<string> {
	const salt = crypto.randomBytes(16);
	const hash = await scrypt(password, salt, 64);
	return `scrypt$${salt.toString("base64")}$${hash.toString("base64")}`;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
	const [kind, salt, hash] = stored.split("$");
	if (kind !== "scrypt" || !salt || !hash) return false;
	const expected = Buffer.from(hash, "base64");
	const actual = await scrypt(password, Buffer.from(salt, "base64"), expected.length);
	return crypto.timingSafeEqual(actual, expected);
}

export const ACCOUNT_MESSAGES = [
	"Use 3 to 32 letters, digits, dots, dashes, or underscores.",
	`Use a password of at least ${PASSWORD_MIN} characters.`,
	"That username is taken.",
	"Wrong username or password.",
	"Too many tries. Wait 15 minutes and try again.",
	"Could not sign in.",
];

export type AccountResult = { id: string; name: string } | { error: string };

/** A new account with the +10 trial. Refuses a taken name or a weak password. */
export async function register(rawUsername: string, password: string): Promise<AccountResult> {
	const username = rawUsername.trim().toLowerCase();
	if (!USERNAME.test(username)) {
		return { error: "Use 3 to 32 letters, digits, dots, dashes, or underscores." };
	}
	if (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX) {
		return { error: `Use a password of at least ${PASSWORD_MIN} characters.` };
	}

	const passwordHash = await hashPassword(password);
	return db.transaction(async (tx) => {
		const [taken] = await tx.select({ id: users.id }).from(users).where(eq(users.username, username));
		if (taken) return { error: "That username is taken." };

		const user = { id: uuidv4(), username, passwordHash, name: username, createdAt: new Date() };
		await tx.insert(users).values(user);
		await grantTrial(user.id, tx);
		return { id: user.id, name: username };
	});
}

// Compared against when the username does not exist, so a miss costs the same time as a hit.
const DUMMY_HASH = hashPassword(crypto.randomBytes(16).toString("hex"));

/** The account for this username and password, or null. Never says which one was wrong. */
export async function login(rawUsername: string, password: string) {
	const username = rawUsername.trim().toLowerCase();
	const [user] = USERNAME.test(username)
		? await db.select().from(users).where(eq(users.username, username))
		: [];
	const ok = await verifyPassword(password.slice(0, PASSWORD_MAX), user?.passwordHash ?? (await DUMMY_HASH));
	return ok && user ? { id: user.id, name: user.name } : null;
}

export function appUrl(): string {
	return process.env.APP_URL || "http://localhost:3000";
}

/**
 * The passwordless local button exists only for exactly this origin, and never in a
 * production build: a hosted copy that forgets APP_URL must not open a shared login.
 */
export function localLoginAllowed(): boolean {
	return appUrl() === "http://localhost:3000" && process.env.NODE_ENV !== "production";
}

/** Free refills go to the passwordless local user and nobody else. */
export function localCreditsAllowed(email: string | null): boolean {
	return localLoginAllowed() && email === LOCAL_EMAIL;
}

/**
 * Refills cost nothing to give while the editor is `local`: no paid key stands behind an
 * edit. Any signed-in user may then top up. A paid editor needs Stripe.
 */
export function freeCreditsAllowed(email: string | null): boolean {
	return localCreditsAllowed(email) || providerName === "local";
}
