import "server-only";
import type { EditInput, EditOutput, ImageEditor } from "./types";

export class WaveSpeedEditor implements ImageEditor {
	// eslint-disable-next-line @typescript-eslint/no-unused-vars
	async edit(input: EditInput): Promise<EditOutput> {
		if (!process.env.WAVESPEED_API_KEY) {
			throw new Error("WAVESPEED_API_KEY is not set");
		}
		throw new Error("Not implemented");
	}
}
