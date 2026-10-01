import { GeminiEditor } from "./gemini";
import { LocalEditor } from "./local";
import { MockEditor } from "./mock";
import type { ImageEditor } from "./types";
import { WaveSpeedEditor } from "./wavespeed";

const name = process.env.EDITOR_PROVIDER ?? "mock";
export const providerName = name;
if (name !== "mock" && name !== "local" && name !== "gemini" && name !== "wavespeed") {
	throw new Error(`Unknown EDITOR_PROVIDER: ${name}`);
}

export function getEditor(): ImageEditor {
	if (name === "mock") return new MockEditor();
	if (name === "local") return new LocalEditor();
	if (name === "gemini") return new GeminiEditor();
	if (name === "wavespeed") return new WaveSpeedEditor();
	throw new Error(`Unknown EDITOR_PROVIDER: ${name}`);
}
