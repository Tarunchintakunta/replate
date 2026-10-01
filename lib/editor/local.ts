import "server-only";
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { PROVIDER_TIMEOUT_MS } from "./resize";
import type { EditInput, EditOutput, ImageEditor } from "./types";

/**
 * Edits on this Mac: services/edit/edit.py erases the old words with OpenCV and redraws
 * the new ones in the closest installed font. No network, no key, no model weights.
 * The image keeps its full size; the 1024 cap exists to bound what a paid provider bills.
 */
export class LocalEditor implements ImageEditor {
	async edit(input: EditInput): Promise<EditOutput> {
		// turbopackIgnore: the venv is spawned at runtime and its python symlink leaves the repo.
		const python = path.join(/* turbopackIgnore: true */ process.cwd(), "services/ocr/.venv/bin/python");
		const script = path.join(/* turbopackIgnore: true */ process.cwd(), "services/edit/edit.py");
		if (!existsSync(python)) {
			throw new Error(
				"The local editor is not installed. Run: python3 -m venv services/ocr/.venv && services/ocr/.venv/bin/pip install -r services/ocr/requirements.txt",
			);
		}

		const buffer = await new Promise<Buffer>((resolve, reject) => {
			const child = spawn(python, [script], { timeout: PROVIDER_TIMEOUT_MS });
			const stdout: Buffer[] = [];
			let stderr = "";
			child.stdout.on("data", (chunk) => stdout.push(chunk));
			child.stderr.on("data", (chunk) => {
				stderr += chunk.toString();
			});
			child.on("error", (err) => reject(new Error(`Failed to start the local editor: ${err.message}`)));
			child.on("close", (code, signal) => {
				if (code === 0) {
					resolve(Buffer.concat(stdout));
				} else if (signal) {
					reject(new Error("The local editor timed out"));
				} else {
					// Last line only: a Python traceback ends with the error itself.
					reject(new Error(`The local editor failed: ${stderr.trim().split("\n").pop()}`));
				}
			});
			// A child that dies before reading closes the pipe; `close` reports that failure.
			child.stdin.on("error", () => {});
			child.stdin.end(
				JSON.stringify({
					image: input.imageBuffer.toString("base64"),
					replacements: input.replacements,
				}),
			);
		});

		return { buffer, provider: "local", model: "opencv-inpaint" };
	}
}
