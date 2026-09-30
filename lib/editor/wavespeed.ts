import "server-only";
import { buildPrompt } from "./prompt";
import { fitForProvider, PROVIDER_TIMEOUT_MS, toPng } from "./resize";
import type { EditInput, EditOutput, ImageEditor } from "./types";

// Docs: https://wavespeed.ai/docs/docs-api/wavespeed-ai/flux-kontext-pro
//       https://wavespeed.ai/docs/sync-mode, https://wavespeed.ai/docs/base64-output
const API = "https://api.wavespeed.ai/api/v3";

type Prediction = {
	data?: { status?: string; outputs?: string[]; error?: string };
};

export class WaveSpeedEditor implements ImageEditor {
	async edit(input: EditInput): Promise<EditOutput> {
		const key = process.env.WAVESPEED_API_KEY;
		if (!key) {
			throw new Error("WAVESPEED_API_KEY is not set. Add it to .env or set EDITOR_PROVIDER=mock.");
		}
		const model = process.env.WAVESPEED_EDIT_MODEL || "wavespeed-ai/flux-kontext-pro";

		const fitted = await fitForProvider(input);
		// One request: sync mode waits for the result, base64 output returns the bytes inline.
		// ponytail: the image goes as a data URI. If WaveSpeed rejects it, switch to the
		// documented media upload (POST /media/uploads, PUT, then pass download_url).
		const res = await fetch(`${API}/${model}`, {
			method: "POST",
			headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
			body: JSON.stringify({
				prompt: buildPrompt(fitted.replacements),
				image: `data:image/png;base64,${fitted.imageBuffer.toString("base64")}`,
				enable_sync_mode: true,
				enable_base64_output: true,
			}),
			signal: AbortSignal.timeout(PROVIDER_TIMEOUT_MS),
		});

		if (!res.ok) {
			throw new Error(`WaveSpeed returned HTTP ${res.status}`);
		}

		const { data } = (await res.json()) as Prediction;
		if (data?.status !== "completed") {
			throw new Error(`WaveSpeed prediction ${data?.status ?? "missing"}${data?.error ? `: ${data.error}` : ""}`);
		}
		const output = data.outputs?.[0];
		if (!output) {
			throw new Error("WaveSpeed returned no image");
		}

		return {
			buffer: await toPng(Buffer.from(output.replace(/^data:[^,]*,/, ""), "base64")),
			provider: "wavespeed",
			model,
		};
	}
}
