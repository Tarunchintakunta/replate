"use client";

import { useEffect, useState } from "react";

// The desk in miniature: a line is found, the new words are typed, the poster changes.
const PAIRS = [
	["Summer Sale", "Winter Deals"],
	["OPEN 24 HOURS", "CLOSED TODAY"],
	["Grand Opening", "Coming Soon"],
	["Total $1,249.00", "Total $980.50"],
] as const;

type Phase = "idle" | "select" | "type" | "swap";

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export function ReplaceDemo() {
	const [index, setIndex] = useState(0);
	const [phase, setPhase] = useState<Phase>("idle");
	const [typed, setTyped] = useState(0);
	const [from, to] = PAIRS[index];

	useEffect(() => {
		let live = true;
		(async () => {
			setPhase("idle");
			setTyped(0);
			await wait(700);
			if (!live) return;
			setPhase("select");
			await wait(700);
			if (!live) return;
			setPhase("type");
			for (let n = 1; n <= to.length && live; n++) {
				setTyped(n);
				await wait(55);
			}
			await wait(350);
			if (!live) return;
			setPhase("swap");
			await wait(2600);
			if (live) setIndex((i) => (i + 1) % PAIRS.length);
		})();
		return () => {
			live = false;
		};
	}, [to]);

	const selected = phase !== "idle";
	const swapped = phase === "swap";

	return (
		<div
			className="relative w-full min-w-0 max-w-[480px] rounded-md border border-ink bg-sheet p-3 sm:p-4"
			aria-label={`Example: "${from}" replaced with "${to}"`}
			role="img"
		>
			<div className="flex items-center justify-between font-mono text-[11px] text-ink/60 mb-3">
				<span>poster.png</span>
				<span>
					{swapped ? "replaced" : selected ? "1 line chosen" : "reading…"}
				</span>
			</div>

			{/* The poster */}
			<div className="relative overflow-hidden rounded-[2px] border border-ink bg-green h-36 sm:h-44 flex items-center px-6">
				<div className="absolute inset-x-0 bottom-0 h-1/3 bg-[#e8dec8]" />
				<div className="relative inline-grid">
					{/* Old and new words share one cell so the box fits both. */}
					<span
						key={`old-${index}`}
						className={`col-start-1 row-start-1 font-display text-3xl sm:text-4xl text-paper whitespace-nowrap transition-[clip-path,opacity] duration-500 ease-out ${
							swapped
								? "[clip-path:inset(0_0_0_100%)] opacity-20"
								: "[clip-path:inset(0_0_0_0)]"
						}`}
					>
						{from}
					</span>
					<span
						key={`new-${index}`}
						aria-hidden={!swapped}
						className={`col-start-1 row-start-1 font-display text-3xl sm:text-4xl text-paper whitespace-nowrap transition-[opacity,transform] duration-500 delay-200 ease-out ${
							swapped
								? "opacity-100 translate-y-0"
								: "opacity-0 translate-y-1.5"
						}`}
					>
						{to}
					</span>
					{selected && !swapped && (
						<span
							key={`box-${index}`}
							className="pointer-events-none absolute -inset-x-2 -inset-y-1 border-2 border-[#9fe0c6] rounded-[2px] anim-draw-box"
						/>
					)}
				</div>
			</div>

			{/* The matching row from the Lines list */}
			<div
				className={`mt-3 rounded-md border p-3 transition-colors duration-150 ${
					selected ? "border-green bg-wash" : "border-rule bg-paper"
				}`}
			>
				<div className="flex items-center gap-2 text-sm text-ink">
					<span
						className={`grid place-items-center w-4 h-4 rounded-[3px] border text-[10px] leading-none transition-colors duration-150 ${
							selected ? "bg-green border-green text-paper" : "border-ink/40"
						}`}
						aria-hidden
					>
						{selected ? "✓" : ""}
					</span>
					<span className="font-medium truncate">“{from}”</span>
				</div>
				<div className="mt-2 rounded border border-rule bg-paper px-2 py-1.5 text-sm text-ink min-h-[34px] flex items-center">
					{phase === "idle" || phase === "select" ? (
						<span className="text-ink/40">Replacement</span>
					) : (
						<>
							<span>{to.slice(0, typed)}</span>
							{phase === "type" && (
								<span className="anim-caret ml-px inline-block w-px h-4 bg-ink" />
							)}
						</>
					)}
				</div>
			</div>
		</div>
	);
}
