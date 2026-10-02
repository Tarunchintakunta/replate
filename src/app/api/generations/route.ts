import { desc, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "../../../../db/client";
import { generations, images } from "../../../../db/schema";
import { currentUser } from "../../../../lib/auth/current-user";
import { getEditor, providerName } from "../../../../lib/editor";
import type { ImageEditor } from "../../../../lib/editor/types";
import { GenerationBody, runGeneration } from "../../../../lib/generation/run";

// Playwright forces the failure path with this header. Honored only when NODE_ENV is
// "test", so `pnpm dev` (development) and `pnpm start` (production) ignore it.
const failingEditor: ImageEditor = {
	edit: async () => {
		throw new Error("Forced failure (x-replate-fail)");
	},
};

// Turbopack inlines `process.env.NODE_ENV` (even through a constant key) as "development"
// under `next dev`. Build the key at runtime to read the real process env, which
// Playwright sets to "test".
const NODE_ENV_KEY = ["NODE", "ENV"].join("_");

function editorFor(request: Request): ImageEditor {
	const forced =
		process.env[NODE_ENV_KEY] === "test" &&
		request.headers.get("x-replate-fail") === "1";
	return forced ? failingEditor : getEditor();
}

export async function POST(request: Request) {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}

	const parsed = GenerationBody.safeParse(
		await request.json().catch(() => null),
	);
	if (!parsed.success) {
		return NextResponse.json({ error: "Invalid request." }, { status: 400 });
	}

	const result = await runGeneration(
		user.id,
		parsed.data,
		editorFor(request),
		providerName,
	);
	if (result.status === 200) {
		return NextResponse.json({ id: result.generationId });
	}
	return NextResponse.json({ error: result.error }, { status: result.status });
}

export async function GET(request: Request) {
	const user = await currentUser();
	if (!user) {
		return NextResponse.json({ error: "Sign in first." }, { status: 401 });
	}

	const requested = Number(new URL(request.url).searchParams.get("limit"));
	const limit =
		Number.isInteger(requested) && requested > 0 ? Math.min(requested, 50) : 20;

	const rows = await db
		.select({
			id: generations.id,
			status: generations.status,
			createdAt: generations.createdAt,
			imageId: images.id,
			width: images.width,
			height: images.height,
		})
		.from(generations)
		.innerJoin(images, eq(generations.imageId, images.id))
		.where(eq(generations.userId, user.id))
		.orderBy(desc(generations.createdAt))
		.limit(limit);

	return NextResponse.json({
		generations: rows.map((r) => ({
			id: r.id,
			status: r.status,
			created_at: r.createdAt.toISOString(),
			image: { id: r.imageId, width: r.width, height: r.height },
		})),
	});
}
