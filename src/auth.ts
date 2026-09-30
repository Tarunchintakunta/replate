import "server-only";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import NextAuth from "next-auth";
import type { Provider } from "next-auth/providers";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import {
	appUrl,
	ensureUser,
	LOCAL_EMAIL,
	localLoginAllowed,
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

const providers: Provider[] = [
	Credentials({
		id: "local",
		name: "Local",
		credentials: {},
		// No password: this is the localhost bridge. Refused on any other origin.
		authorize: async () =>
			localLoginAllowed() ? { email: LOCAL_EMAIL, name: "Local Dev" } : null,
	}),
];
if (process.env.AUTH_GOOGLE_ID && process.env.AUTH_GOOGLE_SECRET) {
	providers.push(Google);
}

export const googleEnabled = providers.length > 1;

export const { handlers, auth, signIn, signOut } = NextAuth({
	secret: secret(),
	trustHost: true,
	useSecureCookies: appUrl().startsWith("https://"),
	session: { strategy: "jwt" },
	providers,
	callbacks: {
		jwt({ token, user }) {
			// On sign-in, bind the token to our users row (created with the trial if new).
			if (user?.email) {
				token.sub = ensureUser(user.email, user.name ?? user.email).id;
			}
			return token;
		},
		session({ session, token }) {
			if (token.sub) session.user.id = token.sub;
			return session;
		},
	},
});
