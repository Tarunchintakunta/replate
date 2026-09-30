import sharp from "sharp";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GeminiEditor } from "./gemini";

const tinyPng = () =>
	sharp({ create: { width: 4, height: 4, channels: 3, background: "red" } })
		.png()
		.toBuffer();

const input = async () => ({
	imageBuffer: await sharp({ create: { width: 2048, height: 1024, channels: 3, background: "white" } })
		.png()
		.toBuffer(),
	replacements: [{ from: "SALE", to: "HELLO", x: 100, y: 100, width: 200, height: 50 }],
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.unstubAllEnvs();
});

describe("GeminiEditor", () => {
	it("sends a 1024 PNG with the prompt and returns the image bytes", async () => {
		vi.stubEnv("GEMINI_API_KEY", "test-key");
		const out = await tinyPng();
		const fetchMock = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({
					steps: [
						{
							type: "model_output",
							content: [
								{ type: "text", text: "Here you go" },
								{ type: "image", mime_type: "image/png", data: out.toString("base64") },
							],
						},
					],
				}),
			),
		);
		vi.stubGlobal("fetch", fetchMock);

		const result = await new GeminiEditor().edit(await input());

		expect(result.provider).toBe("gemini");
		expect(result.model).toBe("gemini-2.5-flash-image");
		expect(result.buffer.equals(out)).toBe(true);

		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe("https://generativelanguage.googleapis.com/v1beta/interactions");
		expect(init.headers["x-goog-api-key"]).toBe("test-key");
		expect(init.signal).toBeInstanceOf(AbortSignal);
		const body = JSON.parse(init.body);
		expect(body.model).toBe("gemini-2.5-flash-image");
		// Boxes are scaled with the image: 2048 → 1024 halves them.
		expect(body.input[0].text).toContain('x=50 y=50 width=100 height=25, replace "SALE" with "HELLO"');
		const sent = await sharp(Buffer.from(body.input[1].data, "base64")).metadata();
		expect([sent.width, sent.height]).toEqual([1024, 512]);
	});

	it("throws without a key and never calls fetch", async () => {
		vi.stubEnv("GEMINI_API_KEY", "");
		const fetchMock = vi.fn();
		vi.stubGlobal("fetch", fetchMock);

		await expect(new GeminiEditor().edit(await input())).rejects.toThrow("GEMINI_API_KEY is not set");
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it("throws on an HTTP error or a response without an image", async () => {
		vi.stubEnv("GEMINI_API_KEY", "test-key");
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("nope", { status: 404 })));
		await expect(new GeminiEditor().edit(await input())).rejects.toThrow("HTTP 404");

		vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ steps: [] }))));
		await expect(new GeminiEditor().edit(await input())).rejects.toThrow("no image");
	});
});
