import { NextResponse } from "next/server";
import { db } from "../../../../../db/client";
import { currentUser } from "../../../../../lib/auth/current-user";
import { freeCreditsAllowed } from "../../../../../lib/auth/users";
import { grantLocalPack } from "../../../../../lib/credits/ledger";

// The free refill: the passwordless localhost user, or anyone while the editor is
// `local` and an edit costs nothing. Otherwise the pack goes through Stripe.
export async function POST() {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}
	if (!freeCreditsAllowed(user.email)) {
		return NextResponse.json(
			{ error: "Free credits are not offered here." },
			{ status: 403 },
		);
	}

	await db.transaction((tx) => grantLocalPack(user.id, tx));
	// Form post from /pricing: a relative 303 lands back on the desk on any port.
	return new NextResponse(null, {
		status: 303,
		headers: { Location: "/dashboard" },
	});
}
