import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	// Playwright runs its own dev server next to a developer's `pnpm dev`; separate build dirs keep them apart.
	distDir: process.env.NEXT_DIST_DIR || ".next",
	// Loaded from node_modules at run time: pglite ships a wasm build, pg optional natives.
	serverExternalPackages: ["@electric-sql/pglite", "pg"],
	experimental: {
		// A front domain that forwards to this server (Vercel in front of Railway) posts
		// forms from its own origin. List it here or Next refuses those Server Actions.
		serverActions: {
			allowedOrigins: (process.env.ALLOWED_ORIGINS || "")
				.split(",")
				.filter(Boolean),
		},
	},
};

export default nextConfig;
