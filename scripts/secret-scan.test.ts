import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";

function scan(files: Record<string, string>, env: Record<string, string> = {}) {
	const dir = fs.mkdtempSync(path.join(os.tmpdir(), "secret-scan-"));
	for (const [name, text] of Object.entries(files)) {
		fs.mkdirSync(path.dirname(path.join(dir, name)), { recursive: true });
		fs.writeFileSync(path.join(dir, name), text);
	}
	return spawnSync("pnpm", ["exec", "tsx", "scripts/secret-scan.ts", dir], {
		encoding: "utf8",
		env: { ...process.env, AUTH_SECRET: "", ...env },
	});
}

describe("secret-scan", () => {
	it("passes a clean client dir", () => {
		const result = scan({ "chunks/app.js": "console.log('hello')" });
		expect(result.stderr).toBe("");
		expect(result.status).toBe(0);
	});

	it("fails on a Stripe test key in a client chunk", () => {
		const result = scan({ "chunks/app.js": 'const k = "sk_test_example";' });
		expect(result.status).toBe(1);
		expect(result.stderr).toContain("sk_test_");
	});

	it("fails on the AUTH_SECRET value without printing it", () => {
		const secret = "a-long-auth-secret-value";
		const result = scan({ "chunks/app.js": `x="${secret}"` }, { AUTH_SECRET: secret });
		expect(result.status).toBe(1);
		expect(result.stderr).toContain("AUTH_SECRET value");
		expect(result.stderr).not.toContain(secret);
	});
}, 30_000);
