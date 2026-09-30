"use client";

import { useEffect, useState } from "react";
import { useBalance } from "./useBalance";

const PROVIDER_LABEL: Record<string, string> = {
	mock: "Local preview",
	gemini: "Gemini",
	wavespeed: "WaveSpeed",
};

export function TopBar() {
	const balance = useBalance();
	const [provider, setProvider] = useState("Local preview");

	useEffect(() => {
		fetch("/api/health")
			.then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
			.then((h: { provider: string; keyPresent: boolean }) => {
				const label = PROVIDER_LABEL[h.provider] ?? h.provider;
				setProvider(h.keyPresent ? label : `${label} · no key`);
			})
			.catch(() => {});
	}, []);

	return (
		<header className="h-[56px] border-b border-rule flex items-center justify-between px-4 shrink-0">
			<div className="flex items-center">
				<h1 className="font-display italic text-2xl font-semibold tracking-tight text-ink">
					Replate
				</h1>
			</div>
			<div className="flex items-center gap-4 text-sm">
				<div className="flex items-center gap-2">
					<span className="text-ink">Credits:</span>
					<span
						data-testid="balance"
						className="font-mono bg-wash px-2 py-0.5 rounded text-ink border border-rule"
					>
						{balance ?? "…"}
					</span>
				</div>
				<div
					data-testid="provider"
					className="bg-wash px-2 py-0.5 rounded text-ink border border-rule"
				>
					{provider}
				</div>
			</div>
		</header>
	);
}
