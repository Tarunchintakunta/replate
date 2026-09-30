import { NextResponse } from "next/server";
import { currentUser } from "../../../../lib/auth/current-user";
import { balanceOf } from "../../../../lib/credits/ledger";

export async function GET() {
	const user = await currentUser();
	return NextResponse.json({ balance: balanceOf(user.id) });
}
