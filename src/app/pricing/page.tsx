import Link from "next/link";
import { currentUser } from "../../../lib/auth/current-user";
import {
	freeCreditsAllowed,
	localCreditsAllowed,
} from "../../../lib/auth/users";
import { billingEnabled } from "../../../lib/billing/checkout";

export const dynamic = "force-dynamic";

export default async function PricingPage() {
	const enabled = billingEnabled();
	const user = await currentUser();
	const free = user ? freeCreditsAllowed(user.email) : false;
	const local = user ? localCreditsAllowed(user.email) : false;

	return (
		<main className="flex-1 flex flex-col items-center justify-center p-6 gap-6 bg-paper">
			<h1 className="font-display italic text-4xl font-semibold text-ink">
				Credits
			</h1>
			<div className="border border-rule rounded-md p-6 w-full max-w-xs flex flex-col gap-3 text-center">
				<p className="text-2xl text-ink">
					<span className="font-mono">100</span> credits
				</p>
				<p className="text-ink opacity-70">test price $5</p>
				<p className="text-sm text-ink opacity-70">
					One standard image costs 10 credits.
				</p>
				<form action="/api/billing/checkout" method="post">
					<button
						type="submit"
						disabled={!enabled}
						className="w-full bg-green text-paper py-2 px-4 rounded-md font-medium disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper"
					>
						Buy 100 credits
					</button>
				</form>
				{!enabled && (
					<p className="text-sm text-ink">
						Payments are off until test keys are set.
					</p>
				)}
			</div>
			{free && (
				<form
					action="/api/credits/local"
					method="post"
					className="w-full max-w-xs flex flex-col gap-2 text-center"
				>
					<button
						type="submit"
						className="w-full border border-rule text-ink bg-paper py-2 px-4 rounded-md font-medium focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper"
					>
						{local ? "Add 100 local credits" : "Add 100 credits"}
					</button>
					<p className="text-sm text-ink opacity-70">
						{local
							? "Free on this Mac, for the local user only."
							: "Free while edits run on the built-in editor."}
					</p>
				</form>
			)}
			<Link href="/" className="text-sm text-ink underline underline-offset-2">
				Back to the desk
			</Link>
		</main>
	);
}
