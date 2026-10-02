import { defineConfig } from "drizzle-kit";

// Generating migrations reads only the schema, so no database URL is needed here.
export default defineConfig({
	schema: "./db/schema.ts",
	out: "./db/migrations",
	dialect: "postgresql",
});
