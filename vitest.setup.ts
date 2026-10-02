import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "replate-test-"));

process.env.STORAGE_PATH = tempDir;
// No postgres:// URL: each test file gets its own in-memory Postgres.
process.env.DATABASE_URL = "";

const { migrate } = await import("./db/client");
await migrate();
