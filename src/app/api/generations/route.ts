import { desc, eq } from "drizzle-orm";
import { NextResponse } from "next/server";
import { db } from "../../../../db/client";
import { generations } from "../../../../db/schema";
import { currentUser } from "../../../../lib/auth/current-user";
import { getEditor, providerName } from "../../../../lib/editor";
import { GenerationBody, runGeneration } from "../../../../lib/generation/run";

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
		getEditor(),
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

	const rows = db
		.select({
			id: generations.id,
			status: generations.status,
			createdAt: generations.createdAt,
		})
		.from(generations)
		.where(eq(generations.userId, user.id))
		.orderBy(desc(generations.createdAt))
		.limit(limit)
		.all();

	return NextResponse.json({
		generations: rows.map((r) => ({
			id: r.id,
			status: r.status,
			created_at: r.createdAt.toISOString(),
		})),
	});
}
