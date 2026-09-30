import "server-only";
import type { EditInput, EditOutput, ImageEditor } from "./types";

export class GeminiEditor implements ImageEditor {
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	async edit(input: EditInput): Promise<EditOutput> {
		if (!process.env.GEMINI_API_KEY) {
			throw new Error("GEMINI_API_KEY is not set");
		}
		throw new Error("Not implemented");
	}
}
