import { auth } from "@/auth";
import { Account } from "@/components/Account";
import { SignIn } from "@/components/SignIn";
import { TopBar } from "@/components/TopBar";
import { Workspace } from "@/components/Workspace";

export default async function Home() {
	const session = await auth();

	return (
		<div className="flex flex-col min-h-screen bg-paper w-full">
			{session?.user ? (
				<>
					<TopBar account={<Account />} />
					<Workspace />
				</>
			) : (
				<SignIn />
			)}
		</div>
	);
}
