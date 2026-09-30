import { googleEnabled, signIn } from "@/auth";
import { localLoginAllowed } from "../../lib/auth/users";

const buttonClass =
	"w-full py-2 px-4 rounded-md font-medium focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper";

export function SignIn() {
	const local = localLoginAllowed();

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
			<div className="w-full max-w-xs flex flex-col gap-3">
				{local && (
					<form
						action={async () => {
							"use server";
							await signIn("local", { redirectTo: "/" });
						}}
					>
						<button
							type="submit"
							className={`${buttonClass} bg-green text-paper`}
						>
							Continue as local
						</button>
					</form>
				)}
				{googleEnabled && (
					<form
						action={async () => {
							"use server";
							await signIn("google", { redirectTo: "/" });
						}}
					>
						<button
							type="submit"
							className={`${buttonClass} border border-rule text-ink bg-paper`}
						>
							Continue with Google
						</button>
					</form>
				)}
				{!local && !googleEnabled && (
					<p className="text-sm text-ink text-center">
						Sign-in is not configured for this address.
					</p>
				)}
			</div>
		</main>
	);
}
