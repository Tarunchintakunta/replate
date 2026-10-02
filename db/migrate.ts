import "dotenv/config";
import { migrate } from "./client";

migrate()
	.then(() => {
		console.log("migrations: up to date");
		process.exit(0);
	})
	.catch((err) => {
		console.error("migrations failed:", err);
		process.exit(1);
	});
