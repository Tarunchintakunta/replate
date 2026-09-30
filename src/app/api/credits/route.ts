import { NextResponse } from "next/server";
import { currentUser } from "../../../../lib/auth/current-user";
import { balanceOf } from "../../../../lib/credits/ledger";

export async function GET() {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}
	return NextResponse.json({ balance: balanceOf(user.id) });
}
