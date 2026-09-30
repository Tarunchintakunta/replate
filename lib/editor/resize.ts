import sharp from "sharp";
import type { EditInput } from "./types";

const LONG_EDGE = 1024;

/** Copy of the input with the long edge at most 1024 and boxes scaled to match. Never upscales. */
export async function fitForProvider(input: EditInput): Promise<EditInput> {
	const meta = await sharp(input.imageBuffer).metadata();
	const longest = Math.max(meta.width ?? 0, meta.height ?? 0);
	const scale = longest > LONG_EDGE ? LONG_EDGE / longest : 1;

	const imageBuffer = await sharp(input.imageBuffer)
		.resize({ width: LONG_EDGE, height: LONG_EDGE, fit: "inside", withoutEnlargement: true })
		.png()
		.toBuffer();

	return {
		imageBuffer,
		replacements: input.replacements.map((r) => ({
			...r,
			x: Math.round(r.x * scale),
			y: Math.round(r.y * scale),
			width: Math.max(1, Math.round(r.width * scale)),
			height: Math.max(1, Math.round(r.height * scale)),
		})),
	};
}

/** Providers may answer in JPEG or WebP; the app stores and serves PNG. */
export function toPng(buffer: Buffer): Promise<Buffer> {
	return sharp(buffer).png().toBuffer();
}

export const PROVIDER_TIMEOUT_MS = 60_000;
