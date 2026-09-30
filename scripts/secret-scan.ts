/**
 * Fails when a secret reaches the browser bundle, or when a client component
 * imports a live editor. Run after `pnpm build`:
 *
 *   pnpm exec tsx scripts/secret-scan.ts [clientDir]
 *
 * clientDir defaults to <distDir>/static. Exits 1 on any finding.
 */
import "dotenv/config";
import fs from "node:fs";
import path from "node:path";

const PATTERNS = [
	"GEMINI_API_KEY=",
	"WAVESPEED_API_KEY=",
	"sk_live_",
	"sk_test_",
	"whsec_",
	"BEGIN PRIVATE KEY",
];

// A client file may not import the live editors, directly or through lib/editor's index.
const EDITOR_IMPORT = /from\s+["'][^"']*lib\/editor(?:\/index|\/gemini|\/wavespeed)?["']/;

function* walk(dir: string): Generator<string> {
	if (!fs.existsSync(dir)) return;
	for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
		const full = path.join(dir, entry.name);
		if (entry.isDirectory()) yield* walk(full);
		else yield full;
	}
}

/** Secret strings found in built client assets. */
function scanBundle(dir: string, authSecret = process.env.AUTH_SECRET): string[] {
	const needles = [...PATTERNS];
	if (authSecret && authSecret.length > 8) needles.push(authSecret);

	const findings: string[] = [];
	for (const file of walk(dir)) {
		const text = fs.readFileSync(file, "utf8");
		for (const needle of needles) {
			if (text.includes(needle)) {
				// Never echo the AUTH_SECRET value itself.
				const label = needle === authSecret ? "AUTH_SECRET value" : needle;
				findings.push(`${path.relative(process.cwd(), file)}: ${label}`);
			}
		}
	}
	return findings;
}

/** Source files marked "use client" that import a live editor. */
function scanClientImports(dirs: string[]): string[] {
	const findings: string[] = [];
	for (const dir of dirs) {
		for (const file of walk(dir)) {
			if (!/\.(tsx?|jsx?)$/.test(file)) continue;
			const text = fs.readFileSync(file, "utf8");
			if (/^\s*["']use client["']/.test(text) && EDITOR_IMPORT.test(text)) {
				findings.push(`${path.relative(process.cwd(), file)}: client component imports lib/editor`);
			}
		}
	}
	return findings;
}

const clientDir = process.argv[2] ?? path.join(process.env.NEXT_DIST_DIR || ".next", "static");
if (!fs.existsSync(clientDir)) {
	console.error(`secret-scan: ${clientDir} not found. Run pnpm build first.`);
	process.exit(1);
}

const findings = [...scanBundle(clientDir), ...scanClientImports(["src", "lib"])];
if (findings.length > 0) {
	console.error("secret-scan: FAILED");
	for (const f of findings) console.error(`  ${f}`);
	process.exit(1);
}
console.log(`secret-scan: clean (${clientDir}, src, lib)`);
