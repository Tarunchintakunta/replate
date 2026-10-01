import { NextResponse } from "next/server";
import { db } from "../../../../../db/client";
import { currentUser } from "../../../../../lib/auth/current-user";
import { localCreditsAllowed } from "../../../../../lib/auth/users";
import { grantLocalPack } from "../../../../../lib/credits/ledger";

// The free refill for the passwordless localhost user. Any other user, or any other
// origin, buys the pack through Stripe.
export async function POST() {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}
	if (!localCreditsAllowed(user.email)) {
		return NextResponse.json(
			{ error: "Local credits are only for the local user." },
			{ status: 403 },
		);
	}

	db.transaction((tx) => grantLocalPack(user.id, tx));
	// Form post from /pricing: a relative 303 lands back on the desk on any port.
	return new NextResponse(null, { status: 303, headers: { Location: "/" } });
}
