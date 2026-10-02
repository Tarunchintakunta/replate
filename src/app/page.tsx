import { Account } from "@/components/Account";
import { SignIn } from "@/components/SignIn";
import { TopBar } from "@/components/TopBar";
import { Workspace } from "@/components/Workspace";
import { currentUser } from "../../lib/auth/current-user";

export default async function Home({
	searchParams,
}: {
	searchParams: Promise<{ error?: string }>;
}) {
	// The users row, not just the cookie: a session can outlive its account.
	const user = await currentUser();
	const { error } = await searchParams;

	return (
		<div className="flex flex-col min-h-screen bg-paper w-full">
			{user ? (
				<>
					<TopBar account={<Account />} />
					<Workspace />
				</>
			) : (
				<SignIn error={error} />
			)}
		</div>
	);
}
