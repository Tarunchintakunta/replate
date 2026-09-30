import path from "node:path";
import { and, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../../../../../db/client";
import { images, ocrLines } from "../../../../../../db/schema";
import { currentUser } from "../../../../../../lib/auth/current-user";
import { runOcr } from "../../../../../../lib/ocr/run";

export async function POST(
	_request: Request,
	{ params }: { params: Promise<{ id: string }> },
) {
	const user = await currentUser();
	const { id } = await params;

	const [image] = await db
		.select()
		.from(images)
		.where(and(eq(images.id, id), eq(images.userId, user.id)));

	if (!image) {
		return new NextResponse("Not found", { status: 404 });
	}

	try {
		const fullPath = path.resolve(
			process.env.STORAGE_PATH || "storage",
			image.storageKey,
		);
		const lines = await runOcr(fullPath, image.width, image.height);

		await db.transaction(async (tx) => {
			await tx.delete(ocrLines).where(eq(ocrLines.imageId, id));

			if (lines.length > 0) {
				await tx.insert(ocrLines).values(
					lines.map((line) => ({
						id: uuidv4(),
						imageId: id,
						text: line.text,
						confidence: line.confidence,
						x: line.x,
						y: line.y,
						width: line.width,
						height: line.height,
						replacedWith: null,
					})),
				);
			}
		});

		const storedLines = await db
			.select()
			.from(ocrLines)
			.where(eq(ocrLines.imageId, id));

		return NextResponse.json({ lines: storedLines });
	} catch (err) {
		console.error("OCR Error:", err);
		return new NextResponse("Internal Server Error", { status: 500 });
	}
}
