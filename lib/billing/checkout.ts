import "server-only";
import Stripe from "stripe";
import { appUrl } from "../auth/users";

export function billingEnabled(): boolean {
	return Boolean(
		process.env.STRIPE_SECRET_KEY && process.env.STRIPE_PRICE_PACK && process.env.STRIPE_WEBHOOK_SECRET,
	);
}

/** A test-mode Checkout Session for one 100-credit pack. Returns the Stripe-hosted URL. */
export async function createCheckout(userId: string): Promise<string> {
	const key = process.env.STRIPE_SECRET_KEY;
	const price = process.env.STRIPE_PRICE_PACK;
	if (!key || !price) {
		throw new Error("Payments are off until test keys are set.");
	}
	if (!key.startsWith("sk_test_")) {
		throw new Error("Only Stripe test mode keys are allowed in v1.");
	}

	const session = await new Stripe(key).checkout.sessions.create({
		mode: "payment",
		line_items: [{ price, quantity: 1 }],
		metadata: { userId },
		client_reference_id: userId,
		success_url: `${appUrl()}/dashboard`,
		cancel_url: `${appUrl()}/dashboard`,
	});
	if (!session.url) {
		throw new Error("Stripe returned no checkout URL");
	}
	return session.url;
}
