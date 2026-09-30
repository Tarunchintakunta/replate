import { describe, expect, it } from "vitest";
import { buildPrompt } from "./prompt";

describe("buildPrompt", () => {
	it("builds a prompt for a replacement", () => {
		const text = buildPrompt([
			{ from: "hello", to: "world", x: 10, y: 20, width: 100, height: 50 },
		]);
		expect(text).toContain('replace "hello" with "world"');
		expect(text).toContain("x=10 y=20 width=100 height=50");
	});

	it("builds a prompt for removing text", () => {
		const text = buildPrompt([
			{ from: "hello", to: "", x: 10, y: 20, width: 100, height: 50 },
		]);
		expect(text).toContain("remove the text in the box and reconstruct the background");
		expect(text).toContain("x=10 y=20 width=100 height=50");
	});
});
