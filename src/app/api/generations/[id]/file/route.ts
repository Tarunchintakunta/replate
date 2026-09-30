import { and, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "../../../../../../db/client";
import { generations } from "../../../../../../db/schema";
import { currentUser } from "../../../../../../lib/auth/current-user";
import { readPng } from "../../../../../../lib/images/store";

export async function GET(
	_request: Request,
	{ params }: { params: Promise<{ id: string }> },
) {
	const user = await currentUser();
	if (!user) {
		return new NextResponse("Unauthorized", { status: 401 });
	}
	const { id } = await params;

	const row = db
		.select()
		.from(generations)
		.where(and(eq(generations.id, id), eq(generations.userId, user.id)))
		.get();
	if (!row?.outputKey) {
		return new NextResponse("Not found", { status: 404 });
	}

	try {
		const buffer = await readPng(row.outputKey);
		return new NextResponse(new Uint8Array(buffer), {
			headers: {
				"Content-Type": "image/png",
				"Content-Disposition": `attachment; filename="replate-${id}.png"`,
				"Cache-Control": "private, max-age=31536000, immutable",
			},
		});
	} catch {
		return new NextResponse("Not found", { status: 404 });
	}
}
