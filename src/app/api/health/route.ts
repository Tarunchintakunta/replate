import { NextResponse } from "next/server";
import { providerName } from "../../../../lib/editor";

const KEY_ENV: Record<string, string | undefined> = {
	gemini: "GEMINI_API_KEY",
	wavespeed: "WAVESPEED_API_KEY",
};

// Reports which editor is active and whether its key is set. Never returns the key.
export function GET() {
	const env = KEY_ENV[providerName];
	return NextResponse.json({
		provider: providerName,
		keyPresent: env ? Boolean(process.env[env]) : true,
	});
}
