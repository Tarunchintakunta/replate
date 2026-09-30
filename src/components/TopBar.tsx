"use client";

import { useEffect, useState } from "react";

export function TopBar() {
	const [balance, setBalance] = useState<number | null>(null);

	useEffect(() => {
		fetch("/api/credits")
			.then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
			.then((data) => setBalance(data.balance))
			.catch(() => setBalance(null));
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
						{balance !== null ? balance : "..."}
					</span>
				</div>
				<div className="bg-wash px-2 py-0.5 rounded text-ink border border-rule">
					Local preview
				</div>
			</div>
		</header>
	);
}
