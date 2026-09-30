import type { NextConfig } from "next";

const nextConfig: NextConfig = {
	// Playwright runs its own dev server next to a developer's `pnpm dev`; separate build dirs keep them apart.
	distDir: process.env.NEXT_DIST_DIR || ".next",
};

export default nextConfig;
