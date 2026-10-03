import { redirect } from "next/navigation";
import { AuthPage } from "@/components/AuthPage";
import { currentUser } from "../../../lib/auth/current-user";

export const dynamic = "force-dynamic";

export default async function Page({
	searchParams,
}: {
	searchParams: Promise<{ error?: string }>;
}) {
	if (await currentUser()) redirect("/dashboard");
	const { error } = await searchParams;
	return <AuthPage mode="signup" error={error} />;
}
