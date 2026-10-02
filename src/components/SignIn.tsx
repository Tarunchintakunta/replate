import { redirect } from "next/navigation";
import { AuthError } from "next-auth";
import { signIn } from "@/auth";
import {
	ACCOUNT_MESSAGES,
	localLoginAllowed,
	PASSWORD_MIN,
} from "../../lib/auth/users";

const buttonClass =
	"w-full py-2 px-4 rounded-md font-medium focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper";
const inputClass =
	"border border-rule rounded px-3 py-2 text-sm bg-paper text-ink focus:outline-none focus:border-green focus:ring-1 focus:ring-green";

async function withPassword(form: FormData) {
	"use server";
	try {
		await signIn("password", {
			username: form.get("username"),
			password: form.get("password"),
			intent: form.get("intent"),
			redirectTo: "/",
		});
	} catch (err) {
		// A successful sign-in throws a redirect; only Auth.js errors land here.
		if (!(err instanceof AuthError)) throw err;
		const code = "code" in err && typeof err.code === "string" ? err.code : "";
		redirect(`/?error=${encodeURIComponent(code || "Could not sign in.")}`);
	}
}

export function SignIn({ error: given }: { error?: string }) {
	const local = localLoginAllowed();
	// The message rides in the URL, so only our own wording is shown.
	const error =
		given && (ACCOUNT_MESSAGES.includes(given) ? given : "Could not sign in.");

	return (
		<main className="flex-1 flex flex-col items-center justify-center p-6 gap-8">
			<div className="text-center">
				<h1 className="font-display italic text-5xl font-semibold tracking-tight text-ink">
					Replate
				</h1>
				<p className="mt-2 text-lg text-ink">
					Change the words. Keep the picture.
				</p>
			</div>
			<div className="w-full max-w-xs flex flex-col gap-4">
				<form action={withPassword} className="flex flex-col gap-3">
					<label className="flex flex-col gap-1 text-sm text-ink">
						Username
						<input
							name="username"
							autoComplete="username"
							required
							minLength={3}
							maxLength={32}
							className={inputClass}
						/>
					</label>
					<label className="flex flex-col gap-1 text-sm text-ink">
						Password
						<input
							name="password"
							type="password"
							autoComplete="current-password"
							required
							minLength={PASSWORD_MIN}
							maxLength={128}
							className={inputClass}
						/>
					</label>
					{error && (
						<p role="alert" className="text-sm text-danger">
							{error}
						</p>
					)}
					<button
						type="submit"
						name="intent"
						value="signin"
						className={`${buttonClass} bg-green text-paper`}
					>
						Sign in
					</button>
					<button
						type="submit"
						name="intent"
						value="signup"
						className={`${buttonClass} border border-rule text-ink bg-paper`}
					>
						Create account
					</button>
				</form>
				{local && (
					<form
						action={async () => {
							"use server";
							await signIn("local", { redirectTo: "/" });
						}}
					>
						<button
							type="submit"
							className={`${buttonClass} border border-rule text-ink bg-paper`}
						>
							Continue as local
						</button>
					</form>
				)}
			</div>
		</main>
	);
}
