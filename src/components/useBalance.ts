"use client";

import { useCallback, useEffect, useState } from "react";

const EVENT = "replate:credits-changed";

/** Current credit balance from GET /api/credits. null while loading or on error. */
export function useBalance(): number | null {
	const [balance, setBalance] = useState<number | null>(null);

	const load = useCallback(() => {
		fetch("/api/credits")
			.then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
			.then((data) => setBalance(data.balance))
			.catch(() => setBalance(null));
	}, []);

	useEffect(() => {
		load();
		window.addEventListener(EVENT, load);
		return () => window.removeEventListener(EVENT, load);
	}, [load]);

	return balance;
}

export function creditsChanged() {
	window.dispatchEvent(new Event(EVENT));
}
