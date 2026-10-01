import { auth, signOut } from "@/auth";

export async function Account() {
	const session = await auth();
	if (!session?.user) return null;

	return (
		<form
			action={async () => {
				"use server";
				await signOut({ redirectTo: "/" });
			}}
			className="flex items-center gap-2"
		>
			<span className="hidden sm:inline text-ink opacity-70 truncate">
				{session.user.email}
			</span>
			<button
				type="submit"
				className="text-ink underline underline-offset-2 rounded focus:outline-none focus:ring-2 focus:ring-green"
			>
				Sign out
			</button>
		</form>
	);
}
