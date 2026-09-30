import { eq } from "drizzle-orm";
import Stripe from "stripe";
import { db } from "../../db/client";
import { stripeEvents, users } from "../../db/schema";
import { creditPack } from "../credits/ledger";

export type WebhookResult = { status: 200 | 400; message: string };

/** Verify a Stripe webhook and credit the pack once per event id. */
export function handleStripeWebhook(
	rawBody: string,
	signature: string | null,
	secret: string,
): WebhookResult {
	let event: Stripe.Event;
	try {
		event = Stripe.webhooks.constructEvent(rawBody, signature ?? "", secret);
	} catch {
		return { status: 400, message: "Invalid signature" };
	}

	if (event.type !== "checkout.session.completed") {
		return { status: 200, message: "Ignored" };
	}

	const session = event.data.object;
	const userId = session.metadata?.userId;
	if (session.payment_status !== "paid" || !userId) {
		return { status: 200, message: "Not a paid pack" };
	}

	return db.transaction((tx) => {
		if (!tx.select().from(users).where(eq(users.id, userId)).get()) {
			return { status: 200 as const, message: "Unknown user" };
		}
		if (tx.select().from(stripeEvents).where(eq(stripeEvents.id, event.id)).get()) {
			return { status: 200 as const, message: "Already processed" };
		}
		tx.insert(stripeEvents).values({ id: event.id, receivedAt: new Date() }).run();
		creditPack(userId, event.id, tx);
		return { status: 200 as const, message: "Credited" };
	});
}
