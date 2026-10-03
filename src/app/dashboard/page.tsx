import { redirect } from "next/navigation";
import { Account } from "@/components/Account";
import { TopBar } from "@/components/TopBar";
import { Workspace } from "@/components/Workspace";
import { currentUser } from "../../../lib/auth/current-user";

export const dynamic = "force-dynamic";

export default async function Dashboard() {
	// The users row, not just the cookie: a session can outlive its account.
	const user = await currentUser();
	if (!user) redirect("/signin");

	return (
		<div className="flex flex-col min-h-screen bg-paper w-full">
			<TopBar account={<Account />} />
			<div className="rise w-full max-w-6xl mx-auto px-4 pt-6 lg:px-8 lg:pt-8">
				<h2 className="font-display text-2xl sm:text-3xl font-semibold tracking-tight text-ink">
					Hello,{" "}
					<span className="italic text-green">
						{user.username ?? user.name}
					</span>
				</h2>
				<p className="mt-1 text-sm text-ink/70">
					Upload a picture, choose the lines, type the new words.
				</p>
			</div>
			<Workspace />
		</div>
	);
}
