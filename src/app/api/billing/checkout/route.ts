import { NextResponse } from "next/server";
import { currentUser } from "../../../../../lib/auth/current-user";
import {
	billingEnabled,
	createCheckout,
} from "../../../../../lib/billing/checkout";

export async function POST() {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}
	if (!billingEnabled()) {
		return NextResponse.json(
			{ error: "Payments are off until test keys are set." },
			{ status: 503 },
		);
	}

	try {
		// Form post from /pricing: 303 sends the browser on to Stripe Checkout.
		return NextResponse.redirect(await createCheckout(user.id), 303);
	} catch (err) {
		console.error("Checkout failed:", err instanceof Error ? err.message : err);
		return NextResponse.json(
			{ error: "Could not start checkout." },
			{ status: 502 },
		);
	}
}
