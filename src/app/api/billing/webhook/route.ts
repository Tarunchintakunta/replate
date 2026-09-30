import { NextResponse } from "next/server";
import { handleStripeWebhook } from "../../../../../lib/billing/webhook";

export async function POST(request: Request) {
	const secret = process.env.STRIPE_WEBHOOK_SECRET;
	if (!secret) {
		return NextResponse.json(
			{ error: "Webhook secret not set" },
			{ status: 503 },
		);
	}

	// The signature covers the exact bytes, so read the raw body.
	const result = handleStripeWebhook(
		await request.text(),
		request.headers.get("stripe-signature"),
		secret,
	);
	return NextResponse.json(
		{ message: result.message },
		{ status: result.status },
	);
}
