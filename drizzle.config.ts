import * as dotenv from "dotenv";
import { defineConfig } from "drizzle-kit";

dotenv.config();

export default defineConfig({
	schema: "./db/schema.ts",
	out: "./db/migrations",
	dialect: "sqlite",
	dbCredentials: {
		url: process.env.DATABASE_URL || "file:data/replate.db",
	},
});
