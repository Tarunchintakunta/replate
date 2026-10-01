import { and, count, eq, gt, inArray } from "drizzle-orm";
import { v4 as uuidv4 } from "uuid";
import { z } from "zod";
import { db } from "../../db/client";
import {
	generationReplacements,
	generations,
	images,
	ocrLines,
} from "../../db/schema";
import { balanceOf, debitGeneration, GENERATION_COST } from "../credits/ledger";
import type { ImageEditor } from "../editor/types";
import { deletePng, generationKey, readPng, writePng } from "../images/store";

export const GenerationBody = z.object({
	imageId: z.string().uuid(),
	lines: z
		.array(
			z.object({
				lineId: z.string().uuid().nullable(),
				from: z.string().max(200),
				to: z.string().max(200),
				box: z.object({
					x: z.number().int().nonnegative(),
					y: z.number().int().nonnegative(),
					width: z.number().int().positive(),
					height: z.number().int().positive(),
				}),
			}),
		)
		.min(1)
		.max(20),
});
export type GenerationRequest = z.infer<typeof GenerationBody>;

export type GenerationResult =
	| { status: 200; generationId: string }
	| { status: 402 | 404 | 409 | 429 | 500 | 502; error: string };

const RATE_LIMIT_PER_HOUR = 10;
const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);

// ponytail: in-process lock, fine for one local Next.js server. Move to a DB row if this ever runs multi-process.
const inFlight = new Set<string>();

export async function runGeneration(
	userId: string,
	body: GenerationRequest,
	editor: ImageEditor,
	providerName: string,
): Promise<GenerationResult> {
	if (inFlight.has(userId)) {
		return { status: 409, error: "A replacement is already running." };
	}
	inFlight.add(userId);
	try {
		return await run(userId, body, editor, providerName);
	} finally {
		inFlight.delete(userId);
	}
}

async function run(
	userId: string,
	body: GenerationRequest,
	editor: ImageEditor,
	providerName: string,
): Promise<GenerationResult> {
	const image = db
		.select()
		.from(images)
		.where(and(eq(images.id, body.imageId), eq(images.userId, userId)))
		.get();
	if (!image) return { status: 404, error: "Image not found." };

	// The limit exists so a loop cannot drain a paid key. The local editor has no key to drain.
	if (providerName !== "local") {
		const hourAgo = new Date(Date.now() - 60 * 60 * 1000);
		const recent = db
			.select({ n: count() })
			.from(generations)
			.where(and(eq(generations.userId, userId), gt(generations.createdAt, hourAgo)))
			.get();
		if ((recent?.n ?? 0) >= RATE_LIMIT_PER_HOUR) {
			return { status: 429, error: "Too many attempts. Try again in an hour." };
		}
	}

	if (balanceOf(userId) < GENERATION_COST) {
		return { status: 402, error: "No credits left." };
	}

	const generationId = uuidv4();
	const createdAt = new Date();

	let output: Awaited<ReturnType<ImageEditor["edit"]>>;
	try {
		output = await editor.edit({
			imageBuffer: await readPng(image.storageKey),
			replacements: body.lines.map((l) => ({ from: l.from, to: l.to, ...l.box })),
		});
		if (!output.buffer.subarray(0, 8).equals(PNG_MAGIC)) {
			throw new Error("Editor returned something that is not a PNG");
		}
	} catch (err) {
		const message = err instanceof Error ? err.message : String(err);
		db.insert(generations)
			.values({
				id: generationId,
				userId,
				imageId: image.id,
				provider: providerName,
				model: "",
				status: "failed",
				error: message,
				createdAt,
			})
			.run();
		return { status: 502, error: `The edit failed: ${message}. Try again.` };
	}

	const outputKey = generationKey(generationId);
	await writePng(outputKey, output.buffer);

	// Drawn boxes carry client-made ids; only keep ids that are real lines of this image.
	const claimed = body.lines.flatMap((l) => (l.lineId ? [l.lineId] : []));
	const known = new Set(
		claimed.length === 0
			? []
			: db
					.select({ id: ocrLines.id })
					.from(ocrLines)
					.where(and(eq(ocrLines.imageId, image.id), inArray(ocrLines.id, claimed)))
					.all()
					.map((r) => r.id),
	);

	try {
		db.transaction((tx) => {
			tx.insert(generations)
				.values({
					id: generationId,
					userId,
					imageId: image.id,
					provider: output.provider,
					model: output.model,
					status: "succeeded",
					outputKey,
					createdAt,
				})
				.run();
			tx.insert(generationReplacements)
				.values(
					body.lines.map((l) => ({
						generationId,
						ocrLineId: l.lineId && known.has(l.lineId) ? l.lineId : null,
						fromText: l.from,
						toText: l.to,
						...l.box,
					})),
				)
				.run();
			debitGeneration(userId, generationId, tx);
		});
	} catch (err) {
		await deletePng(outputKey);
		console.error("Generation commit failed:", err);
		return { status: 500, error: "Could not save the result. No credits were spent." };
	}

	return { status: 200, generationId };
}
