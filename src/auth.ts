import "server-only";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import NextAuth, { CredentialsSignin } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import {
	appUrl,
	ensureUser,
	LOCAL_EMAIL,
	localLoginAllowed,
	login,
	register,
} from "../lib/auth/users";

// Without AUTH_SECRET in .env, keep a random one in data/ (gitignored) so a
// fresh clone can sign in locally and sessions survive a restart.
function secret(): string {
	if (process.env.AUTH_SECRET) return process.env.AUTH_SECRET;
	const file = path.resolve("data/auth-secret");
	try {
		return fs.readFileSync(file, "utf8").trim();
	} catch {
		const value = crypto.randomBytes(32).toString("base64url");
		fs.mkdirSync(path.dirname(file), { recursive: true });
		fs.writeFileSync(file, value, { mode: 0o600 });
		return value;
	}
}

/** Carries a message the sign-in page can show. Auth.js passes `code` through. */
class AccountError extends CredentialsSignin {
	constructor(message: string) {
		super();
		this.code = message;
	}
}

// ponytail: in-process counter, right for one container. Move to the database if the
// app ever runs on more than one instance.
const FAILURE_LIMIT = 10;
const FAILURE_WINDOW_MS = 15 * 60 * 1000;
const failures = new Map<string, { count: number; since: number }>();

function tooManyFailures(username: string): boolean {
	const entry = failures.get(username);
	if (!entry || Date.now() - entry.since > FAILURE_WINDOW_MS) return false;
	return entry.count >= FAILURE_LIMIT;
}

function noteFailure(username: string) {
	const entry = failures.get(username);
	if (!entry || Date.now() - entry.since > FAILURE_WINDOW_MS) {
		failures.set(username, { count: 1, since: Date.now() });
	} else {
		entry.count += 1;
	}
}

export const { handlers, auth, signIn, signOut } = NextAuth({
	secret: secret(),
	trustHost: true,
	useSecureCookies: appUrl().startsWith("https://"),
	session: { strategy: "jwt" },
	providers: [
		Credentials({
			id: "local",
			name: "Local",
			credentials: {},
			// No password: this is the localhost bridge. Refused on any other origin.
			authorize: async () => {
				if (!localLoginAllowed()) return null;
				const user = await ensureUser(LOCAL_EMAIL, "Local Dev");
				return { id: user.id, email: LOCAL_EMAIL, name: user.name };
			},
		}),
		Credentials({
			id: "password",
			name: "Username and password",
			credentials: { username: {}, password: {}, intent: {} },
			authorize: async (given) => {
				const username = String(given.username ?? "")
					.trim()
					.toLowerCase();
				const password = String(given.password ?? "");

				if (given.intent === "signup") {
					const result = await register(username, password);
					if ("error" in result) throw new AccountError(result.error);
					return { id: result.id, name: result.name };
				}

				if (tooManyFailures(username)) {
					throw new AccountError(
						"Too many tries. Wait 15 minutes and try again.",
					);
				}
				const user = await login(username, password);
				if (!user) {
					noteFailure(username);
					throw new AccountError("Wrong username or password.");
				}
				failures.delete(username);
				return user;
			},
		}),
	],
	callbacks: {
		jwt({ token, user }) {
			// Every provider returns our users row id.
			if (user?.id) token.sub = user.id;
			return token;
		},
		session({ session, token }) {
			if (token.sub) session.user.id = token.sub;
			return session;
		},
	},
});
