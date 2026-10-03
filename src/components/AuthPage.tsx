import Link from "next/link";
import { redirect } from "next/navigation";
import { AuthError } from "next-auth";
import { signIn } from "@/auth";
import {
	ACCOUNT_MESSAGES,
	localLoginAllowed,
	PASSWORD_MIN,
} from "../../lib/auth/users";
import { ReplaceDemo } from "./landing/ReplaceDemo";

type Mode = "signin" | "signup";

const buttonClass =
	"w-full py-2.5 px-4 rounded-md font-medium transition-transform duration-150 hover:-translate-y-px active:translate-y-0 focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper";
const inputClass =
	"border border-rule rounded-md px-3 py-2.5 text-base bg-sheet text-ink transition-colors duration-150 focus:outline-none focus:border-green focus:ring-1 focus:ring-green";

const COPY = {
	signin: {
		title: "Welcome back",
		lead: "Sign in to pick up where you left off.",
		submit: "Sign in",
		other: ["New here?", "Create an account", "/signup"],
	},
	signup: {
		title: "Create your account",
		lead: "10 free credits, enough for your first image.",
		submit: "Create account",
		other: ["Already have an account?", "Sign in", "/signin"],
	},
} as const;

async function withPassword(form: FormData) {
	"use server";
	const mode: Mode = form.get("intent") === "signup" ? "signup" : "signin";
	try {
		await signIn("password", {
			username: form.get("username"),
			password: form.get("password"),
			intent: mode,
			redirectTo: "/dashboard",
		});
	} catch (err) {
		// A successful sign-in throws a redirect; only Auth.js errors land here.
		if (!(err instanceof AuthError)) throw err;
		const code = "code" in err && typeof err.code === "string" ? err.code : "";
		redirect(
			`/${mode}?error=${encodeURIComponent(code || "Could not sign in.")}`,
		);
	}
}

export function AuthPage({
	mode,
	error: given,
}: {
	mode: Mode;
	error?: string;
}) {
	const local = mode === "signin" && localLoginAllowed();
	const copy = COPY[mode];
	// The message rides in the URL, so only our own wording is shown.
	const error =
		given && (ACCOUNT_MESSAGES.includes(given) ? given : "Could not sign in.");

	return (
		<div className="min-h-screen grid lg:grid-cols-2 bg-paper">
			<aside className="hidden lg:flex flex-col justify-between border-r border-rule bg-sheet p-10">
				<Link
					href="/"
					className="font-display italic text-3xl font-semibold tracking-tight text-ink"
				>
					Replate
				</Link>
				<div className="rise flex justify-center">
					<ReplaceDemo />
				</div>
				<p className="font-display text-2xl text-ink">
					Change the words.{" "}
					<span className="italic text-green">Keep the picture.</span>
				</p>
			</aside>

			<main className="flex flex-col items-center justify-center px-6 py-12">
				<Link
					href="/"
					className="lg:hidden mb-10 font-display italic text-4xl font-semibold tracking-tight text-ink"
				>
					Replate
				</Link>
				<div className="rise w-full max-w-sm">
					<h1 className="font-display text-4xl font-semibold tracking-tight text-ink">
						{copy.title}
					</h1>
					<p className="mt-2 text-ink/70">{copy.lead}</p>

					<form action={withPassword} className="mt-8 flex flex-col gap-4">
						<input type="hidden" name="intent" value={mode} />
						<label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
							Username
							<input
								name="username"
								autoComplete="username"
								autoCapitalize="none"
								spellCheck={false}
								required
								minLength={3}
								maxLength={32}
								className={inputClass}
							/>
						</label>
						<label className="flex flex-col gap-1.5 text-sm font-medium text-ink">
							Password
							<input
								name="password"
								type="password"
								autoComplete={
									mode === "signup" ? "new-password" : "current-password"
								}
								required
								minLength={PASSWORD_MIN}
								maxLength={128}
								className={inputClass}
							/>
							{mode === "signup" && (
								<span className="font-normal text-xs text-ink/60">
									At least {PASSWORD_MIN} characters.
								</span>
							)}
						</label>
						{error && (
							<p
								role="alert"
								className="rounded-md border border-danger/30 bg-danger/5 px-3 py-2 text-sm text-danger"
							>
								{error}
							</p>
						)}
						<button
							type="submit"
							className={`${buttonClass} mt-2 bg-green text-paper`}
						>
							{copy.submit}
						</button>
					</form>

					{local && (
						<form
							className="mt-3"
							action={async () => {
								"use server";
								await signIn("local", { redirectTo: "/dashboard" });
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

					<p className="mt-8 text-sm text-ink/70">
						{copy.other[0]}{" "}
						<Link
							href={copy.other[2]}
							className="font-medium text-green underline underline-offset-4"
						>
							{copy.other[1]}
						</Link>
					</p>
				</div>
			</main>
		</div>
	);
}
