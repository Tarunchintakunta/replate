import { and, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "../../../../../../db/client";
import { images } from "../../../../../../db/schema";
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

	const [image] = await db
		.select()
		.from(images)
		.where(and(eq(images.id, id), eq(images.userId, user.id)));

	if (!image) {
		return new NextResponse("Not found", { status: 404 });
	}

	try {
		const buffer = await readPng(image.storageKey);
		return new NextResponse(new Uint8Array(buffer), {
			headers: {
				"Content-Type": "image/png",
				"Cache-Control": "public, max-age=31536000, immutable",
			},
		});
	} catch {
		return new NextResponse("Not found", { status: 404 });
	}
}
