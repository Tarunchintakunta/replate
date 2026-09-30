"use client";

import { useCallback, useEffect, useState } from "react";
import { creditsChanged, useBalance } from "./useBalance";
import type { Line } from "./Workspace";

const COST = 10;

type Recent = { id: string; status: string; created_at: string };

interface GenerateBarProps {
	imageId: string | null;
	lines: Line[];
	resultId: string | null;
	onResult: (generationId: string | null) => void;
}

export function GenerateBar({
	imageId,
	lines,
	resultId,
	onResult,
}: GenerateBarProps) {
	const balance = useBalance();
	const [running, setRunning] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const [recent, setRecent] = useState<Recent[]>([]);

	const loadRecent = useCallback(() => {
		fetch("/api/generations?limit=20")
			.then((res) => (res.ok ? res.json() : Promise.reject(res.status)))
			.then((data) => setRecent(data.generations))
			.catch(() => setRecent([]));
	}, []);

	useEffect(loadRecent, [loadRecent]);

	const checked = lines.filter((l) => l.checked);
	const noCredits = balance !== null && balance < COST;
	const disabled =
		!imageId ||
		checked.length === 0 ||
		running ||
		noCredits ||
		balance === null;

	const generate = async () => {
		if (!imageId) return;
		setRunning(true);
		setError(null);
		try {
			const res = await fetch("/api/generations", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					imageId,
					lines: checked.map((l) => ({
						lineId: l.detected ? l.id : null,
						from: l.text,
						to: l.replacement,
						box: { x: l.x, y: l.y, width: l.width, height: l.height },
					})),
				}),
			});
			const data = await res.json().catch(() => ({}));
			if (!res.ok) {
				setError(data.error ?? "Something went wrong. Try again.");
				return;
			}
			onResult(data.id);
		} catch {
			setError("Something went wrong. Try again.");
		} finally {
			setRunning(false);
			creditsChanged();
			loadRecent();
		}
	};

	let label = "Replace text";
	if (running) label = "Replacing…";
	else if (noCredits) label = "No credits left.";

	return (
		<div className="border-t border-rule pt-4 flex flex-col gap-2">
			{error && (
				<p role="alert" className="text-sm text-danger">
					{error}
				</p>
			)}
			<button
				type="button"
				onClick={generate}
				disabled={disabled}
				className="bg-green text-paper py-2 px-4 rounded-md font-medium disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper transition-shadow"
			>
				{label}
			</button>
			<div className="text-sm text-center text-ink opacity-70">
				{COST} credits
			</div>
			<p className="text-xs text-center text-ink opacity-70">
				Font and background matching is best-effort.
			</p>
			{resultId && (
				<a
					href={`/api/generations/${resultId}/file`}
					download={`replate-${resultId}.png`}
					className="text-sm text-center text-green underline underline-offset-2 focus:outline-none focus:ring-2 focus:ring-green rounded"
				>
					Download PNG
				</a>
			)}

			{recent.length > 0 && (
				<div className="mt-4">
					<h2 className="font-semibold text-ink text-sm mb-2">Recent</h2>
					<ul className="flex flex-col gap-1 text-sm">
						{recent.map((g) => (
							<li key={g.id}>
								{g.status === "succeeded" ? (
									<button
										type="button"
										onClick={() => onResult(g.id)}
										className={`w-full text-left px-2 py-1 rounded border focus:outline-none focus:ring-2 focus:ring-green ${
											g.id === resultId ? "border-green bg-wash" : "border-rule"
										}`}
									>
										{new Date(g.created_at).toLocaleString()} · succeeded
									</button>
								) : (
									<span className="block px-2 py-1 text-ink opacity-60">
										{new Date(g.created_at).toLocaleString()} · {g.status}
									</span>
								)}
							</li>
						))}
					</ul>
				</div>
			)}
		</div>
	);
}
