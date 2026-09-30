import Stripe from "stripe";
import { v4 as uuidv4 } from "uuid";
import { describe, expect, it } from "vitest";
import { ensureUser } from "../auth/users";
import { balanceOf } from "../credits/ledger";
import { handleStripeWebhook } from "./webhook";

// A label, not a credential (SPEC-billing).
const SECRET = "whsec_test_fixture_not_a_real_secret";

function completedEvent(userId: string, eventId = `evt_${uuidv4()}`) {
	return JSON.stringify({
		id: eventId,
		object: "event",
		type: "checkout.session.completed",
		data: {
			object: {
				id: `cs_${uuidv4()}`,
				object: "checkout.session",
				payment_status: "paid",
				metadata: { userId },
			},
		},
	});
}

const sign = (payload: string, secret = SECRET) =>
	Stripe.webhooks.generateTestHeaderString({ payload, secret });

describe("handleStripeWebhook", () => {
	it("adds 100 once per event id", () => {
		const user = ensureUser(`${uuidv4()}@example.com`, "Buyer");
		const payload = completedEvent(user.id);

		expect(handleStripeWebhook(payload, sign(payload), SECRET).status).toBe(200);
		expect(balanceOf(user.id)).toBe(110);

		expect(handleStripeWebhook(payload, sign(payload), SECRET).status).toBe(200);
		expect(balanceOf(user.id)).toBe(110);
	});

	it("rejects a bad signature and writes nothing", () => {
		const user = ensureUser(`${uuidv4()}@example.com`, "Buyer");
		const payload = completedEvent(user.id);

		expect(handleStripeWebhook(payload, sign(payload, "whsec_wrong"), SECRET).status).toBe(400);
		expect(handleStripeWebhook(payload, null, SECRET).status).toBe(400);
		expect(balanceOf(user.id)).toBe(10);
	});

	it("ignores other event types and unpaid sessions", () => {
		const user = ensureUser(`${uuidv4()}@example.com`, "Buyer");
		const other = JSON.stringify({ id: `evt_${uuidv4()}`, object: "event", type: "invoice.paid", data: { object: {} } });
		expect(handleStripeWebhook(other, sign(other), SECRET).status).toBe(200);

		const unpaid = completedEvent(user.id).replace('"paid"', '"unpaid"');
		expect(handleStripeWebhook(unpaid, sign(unpaid), SECRET).status).toBe(200);
		expect(balanceOf(user.id)).toBe(10);
	});
});
