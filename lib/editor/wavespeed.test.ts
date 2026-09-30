import sharp from "sharp";
import { afterEach, describe, expect, it, vi } from "vitest";
import { WaveSpeedEditor } from "./wavespeed";

const tinyPng = () =>
	sharp({ create: { width: 4, height: 4, channels: 3, background: "blue" } })
		.png()
		.toBuffer();

const input = async () => ({
	imageBuffer: await sharp({ create: { width: 600, height: 300, channels: 3, background: "white" } })
		.png()
		.toBuffer(),
	replacements: [{ from: "SALE", to: "", x: 10, y: 20, width: 100, height: 40 }],
});

afterEach(() => {
	vi.unstubAllGlobals();
	vi.unstubAllEnvs();
});

describe("WaveSpeedEditor", () => {
	it("makes one sync request and returns the base64 output as PNG", async () => {
		vi.stubEnv("WAVESPEED_API_KEY", "test-key");
		const out = await tinyPng();
		const fetchMock = vi.fn().mockResolvedValue(
			new Response(
				JSON.stringify({ data: { status: "completed", outputs: [out.toString("base64")] } }),
			),
		);
		vi.stubGlobal("fetch", fetchMock);

		const result = await new WaveSpeedEditor().edit(await input());

		expect(fetchMock).toHaveBeenCalledTimes(1);
		expect(result.provider).toBe("wavespeed");
		expect(result.model).toBe("wavespeed-ai/flux-kontext-pro");
		expect(result.buffer.equals(out)).toBe(true);

		const [url, init] = fetchMock.mock.calls[0];
		expect(url).toBe("https://api.wavespeed.ai/api/v3/wavespeed-ai/flux-kontext-pro");
		expect(init.headers.Authorization).toBe("Bearer test-key");
		expect(init.signal).toBeInstanceOf(AbortSignal);
		const body = JSON.parse(init.body);
		expect(body.enable_sync_mode).toBe(true);
		expect(body.image.startsWith("data:image/png;base64,")).toBe(true);
		expect(body.prompt).toContain("remove the text in the box and reconstruct the background");
	});

	it("throws without a key and never calls fetch", async () => {
		vi.stubEnv("WAVESPEED_API_KEY", "");
		const fetchMock = vi.fn();
		vi.stubGlobal("fetch", fetchMock);

		await expect(new WaveSpeedEditor().edit(await input())).rejects.toThrow("WAVESPEED_API_KEY is not set");
		expect(fetchMock).not.toHaveBeenCalled();
	});

	it("throws on HTTP errors and failed predictions", async () => {
		vi.stubEnv("WAVESPEED_API_KEY", "test-key");
		vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
		await expect(new WaveSpeedEditor().edit(await input())).rejects.toThrow("HTTP 401");

		vi.stubGlobal(
			"fetch",
			vi.fn().mockResolvedValue(
				new Response(JSON.stringify({ data: { status: "failed", error: "nsfw", outputs: [] } })),
			),
		);
		await expect(new WaveSpeedEditor().edit(await input())).rejects.toThrow("prediction failed: nsfw");
	});
});
