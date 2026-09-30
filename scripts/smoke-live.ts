/**
 * One live edit against the selected provider, to confirm a key works.
 * Costs real money. Not part of `pnpm test` or CI. Run once, only when asked:
 *
 *   EDITOR_PROVIDER=gemini pnpm exec tsx --conditions=react-server scripts/smoke-live.ts
 *
 * Writes the result to storage/smoke-live.png. Never prints the key.
 */
import "dotenv/config";
import fs from "node:fs/promises";
import sharp from "sharp";
import { getEditor, providerName } from "../lib/editor";

async function main() {
	if (providerName === "mock") {
		throw new Error("EDITOR_PROVIDER is mock. Set it to gemini or wavespeed for a live smoke test.");
	}

	const fixture = await sharp({
		create: { width: 600, height: 300, channels: 3, background: "#f3efe6" },
	})
		.composite([
			{
				input: Buffer.from(
					'<svg width="600" height="300"><text x="60" y="170" font-size="72" font-family="sans-serif" fill="#1c1915">SALE</text></svg>',
				),
			},
		])
		.png()
		.toBuffer();

	const started = Date.now();
	const out = await getEditor().edit({
		imageBuffer: fixture,
		replacements: [{ from: "SALE", to: "HELLO", x: 50, y: 100, width: 220, height: 90 }],
	});

	await fs.mkdir("storage", { recursive: true });
	await fs.writeFile("storage/smoke-live.png", out.buffer);
	console.log(
		`ok provider=${out.provider} model=${out.model} bytes=${out.buffer.length} ms=${Date.now() - started} -> storage/smoke-live.png`,
	);
}

main().catch((err) => {
	console.error(`smoke-live failed: ${err instanceof Error ? err.message : err}`);
	process.exit(1);
});
