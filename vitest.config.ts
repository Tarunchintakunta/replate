import path from "node:path";
import { defineConfig } from "vitest/config";

export default defineConfig({
	// Server modules start with `import "server-only"`; tests run them as the server would.
	resolve: {
		alias: { "server-only": path.resolve("node_modules/server-only/empty.js") },
	},
	test: {
		setupFiles: ["./vitest.setup.ts"],
		exclude: [
			"**/node_modules/**",
			"**/dist/**",
			"**/cypress/**",
			"**/.{idea,git,cache,output,temp}/**",
			"**/{karma,rollup,webpack,vite,vitest,jest,ava,babel,nyc,cypress,tsup,build,eslint,prettier}.config.*",
			"**/e2e/**",
		],
	},
});
