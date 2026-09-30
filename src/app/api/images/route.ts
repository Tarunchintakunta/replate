import { NextResponse } from "next/server";
import { v4 as uuidv4 } from "uuid";
import { db } from "../../../../db/client";
import { images } from "../../../../db/schema";
import { currentUser } from "../../../../lib/auth/current-user";
import { processUpload } from "../../../../lib/images/accept";
import { originalKey, writePng } from "../../../../lib/images/store";

export async function POST(request: Request) {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}

	try {
		const formData = await request.formData();
		const file = formData.get("file") as Blob | null;
		if (!file) {
			return NextResponse.json({ error: "No file provided" }, { status: 400 });
		}

		const buffer = Buffer.from(await file.arrayBuffer());
		const processed = await processUpload(buffer);

		const imageId = uuidv4();
		const storageKey = originalKey(imageId);

		await writePng(storageKey, processed.buffer);

		await db.insert(images).values({
			id: imageId,
			userId: user.id,
			width: processed.width,
			height: processed.height,
			storageKey,
			createdAt: new Date(),
		});

		return NextResponse.json({
			id: imageId,
			width: processed.width,
			height: processed.height,
		});
	} catch (err: unknown) {
		const error = err as Error;
		if (error.name === "UnsupportedMimeTypeError") {
			return NextResponse.json({ error: error.message }, { status: 415 });
		}
		if (error.name === "FileSizeError") {
			return NextResponse.json({ error: error.message }, { status: 413 });
		}
		if (error.name === "ImageTooLargeError") {
			return NextResponse.json({ error: error.message }, { status: 400 });
		}
		console.error(error);
		return NextResponse.json(
			{ error: "Internal Server Error" },
			{ status: 500 },
		);
	}
}
