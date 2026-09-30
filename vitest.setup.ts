import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "replate-test-"));

process.env.STORAGE_PATH = tempDir;
process.env.DATABASE_URL = path.join(tempDir, "test.db");
