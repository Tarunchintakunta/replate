import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import sharp from "sharp";
import { afterEach, describe, expect, it, vi } from "vitest";
import { runOcr } from "./run";

afterEach(() => {
	vi.unstubAllEnvs();
});

async function renderText(
	file: string,
	w: number,
	h: number,
	bg: string,
	fg: string,
	x: number,
	y: number,
	text: string,
) {
	await sharp({ create: { width: w, height: h, channels: 3, background: bg } })
		.composite([
			{
				input: Buffer.from(
					`<svg width="${w}" height="${h}"><text x="${x}" y="${y}" font-family="sans-serif" font-size="40" fill="${fg}">${text}</text></svg>`,
				),
				top: 0,
				left: 0,
			},
		])
		.png()
		.toFile(file);
}

describe("runOcr modes", () => {
	it("returns the fixture line only when OCR_MODE=fixture", async () => {
		vi.stubEnv("OCR_MODE", "fixture");
		const lines = await runOcr("unused.png", 100, 100);
		expect(lines).toEqual([
			{ text: "SALE", confidence: 1, x: 8, y: 8, width: 48, height: 16 },
		]);
	});

	it("defaults to rapid and explains how to install when the venv is missing", async () => {
		vi.stubEnv("OCR_MODE", "");
		const dir = await fs.mkdtemp(path.join(os.tmpdir(), "replate-noocr-"));
		vi.spyOn(process, "cwd").mockReturnValue(dir);
		try {
			await expect(runOcr("x.png", 10, 10)).rejects.toThrow(
				"OCR is not installed. Run: python3 -m venv services/ocr/.venv",
			);
		} finally {
			vi.restoreAllMocks();
			await fs.rm(dir, { recursive: true, force: true });
		}
	});
});

describe.skipIf(!process.env.RUN_OCR)("runOcr sidecar (RUN_OCR=1)", () => {
	it("returns lines from the script in rapid mode", async () => {
		vi.stubEnv("OCR_MODE", "rapid");
		const file = path.resolve("temp-sidecar-test.png");
		await renderText(file, 400, 200, "#ffffff", "black", 50, 100, "SALE");
		try {
			const lines = await runOcr(file, 400, 200);
			expect(lines.some((l) => l.text.includes("SALE"))).toBe(true);
		} finally {
			await fs.unlink(file).catch(() => {});
		}
	}, 15000); // first model load in the sidecar is slow

	it("reads a headline as one line with every letter inside the box", async () => {
		vi.stubEnv("OCR_MODE", "rapid");
		const file = path.resolve("temp-sidecar-headline.png");
		const svg = `<svg width="1400" height="400"><text x="80" y="250" font-family="serif" font-size="150" fill="#3c1428">Summer Festival</text></svg>`;
		await sharp({ create: { width: 1400, height: 400, channels: 3, background: "#ffc478" } })
			.composite([{ input: Buffer.from(svg), top: 0, left: 0 }])
			.png()
			.toFile(file);
		try {
			const lines = await runOcr(file, 1400, 400);
			// The default detection cuts display type into pieces and drops letters
			// ("ummer", "Fe", "estival"); which letters depends on the serif installed.
			expect(lines.map((l) => l.text)).toEqual(["Summer Festival"]);
			expect(lines[0].x).toBeLessThanOrEqual(110);
			expect(lines[0].width).toBeGreaterThan(800);
		} finally {
			await fs.unlink(file).catch(() => {});
		}
	}, 15000);

	it("returns boxes in image pixels for light text on a dark screenshot", async () => {
		vi.stubEnv("OCR_MODE", "rapid");
		const file = path.resolve("temp-sidecar-dark.png");
		// Baseline at y=900, 40px font: glyphs span roughly y=870..900 from x=100.
		await renderText(
			file,
			800,
			1200,
			"#111827",
			"#e5e7eb",
			100,
			900,
			"Hello from the chat",
		);
		try {
			const lines = await runOcr(file, 800, 1200);
			const line = lines.find((l) => l.text.includes("Hello"));
			expect(line).toBeDefined();
			if (!line) return;
			expect(line.x).toBeGreaterThanOrEqual(85);
			expect(line.x).toBeLessThanOrEqual(115);
			expect(line.y).toBeGreaterThanOrEqual(850);
			expect(line.y).toBeLessThanOrEqual(885);
			expect(line.y + line.height).toBeGreaterThanOrEqual(895);
			expect(line.y + line.height).toBeLessThanOrEqual(920);
			expect(line.width).toBeGreaterThan(250);
		} finally {
			await fs.unlink(file).catch(() => {});
		}
	}, 15000);
});
