import "server-only";
import { buildPrompt } from "./prompt";
import { fitForProvider, PROVIDER_TIMEOUT_MS, toPng } from "./resize";
import type { EditInput, EditOutput, ImageEditor } from "./types";

// Docs: https://ai.google.dev/gemini-api/docs/image-generation (Interactions API)
const ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions";

type Content = { type: string; data?: string; mime_type?: string };
type InteractionResponse = { steps?: { type: string; content?: Content[] }[] };

export class GeminiEditor implements ImageEditor {
	async edit(input: EditInput): Promise<EditOutput> {
		const key = process.env.GEMINI_API_KEY;
		if (!key) {
			throw new Error("GEMINI_API_KEY is not set. Add it to .env or set EDITOR_PROVIDER=mock.");
		}
		const model = process.env.GEMINI_IMAGE_MODEL || "gemini-2.5-flash-image";

		const fitted = await fitForProvider(input);
		const res = await fetch(ENDPOINT, {
			method: "POST",
			headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
			body: JSON.stringify({
				model,
				input: [
					{ type: "text", text: buildPrompt(fitted.replacements) },
					{ type: "image", mime_type: "image/png", data: fitted.imageBuffer.toString("base64") },
				],
			}),
			signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
		});

		if (!res.ok) {
			// Status only: the body can echo the request, which holds the image.
			throw new Error(`Gemini returned HTTP ${res.status}`);
		}

		const body = (await res.json()) as InteractionResponse;
		const image = body.steps
			?.flatMap((s) => s.content ?? [])
			.find((c) => c.type === "image" && c.data);
		if (!image?.data) {
			throw new Error("Gemini returned no image");
		}

		return {
			buffer: await toPng(Buffer.from(image.data, "base64")),
			provider: "gemini",
			model,
		};
	}
}
