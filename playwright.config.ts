import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { defineConfig, devices } from "@playwright/test";

// A private database and storage dir per run, so the trial balance always starts at 10
// and a developer's own `pnpm dev` data is never touched.
const PORT = 3100;
const runDir =
	process.env.REPLATE_E2E_DIR ??
	fs.mkdtempSync(path.join(os.tmpdir(), "replate-e2e-"));
process.env.REPLATE_E2E_DIR = runDir;

export default defineConfig({
	testDir: "./e2e",
	// Specs share one local user and its ledger, so they run in file order.
	fullyParallel: false,
	workers: 1,
	reporter: process.env.CI ? "list" : "html",
	use: {
		baseURL: `http://localhost:${PORT}`,
		trace: "on-first-retry",
	},
	projects: [
		{
			name: "chromium",
			use: { ...devices["Desktop Chrome"] },
		},
	],
	webServer: {
		command: `pnpm exec next dev --port ${PORT}`,
		url: `http://localhost:${PORT}`,
		reuseExistingServer: false,
		timeout: 120_000,
		env: {
			DATABASE_URL: path.join(runDir, "e2e.db"),
			STORAGE_PATH: path.join(runDir, "storage"),
			EDITOR_PROVIDER: "mock",
			OCR_MODE: "fixture",
			NEXT_DIST_DIR: ".next-e2e",
		},
	},
});
