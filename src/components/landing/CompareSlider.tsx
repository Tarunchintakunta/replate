"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Before and after, one over the other. It sweeps by itself until someone drags it;
 * the range input underneath keeps it usable from the keyboard.
 */
export function CompareSlider({
	before,
	after,
	alt,
}: {
	before: string;
	after: string;
	alt: string;
}) {
	const [pos, setPos] = useState(50);
	const [touched, setTouched] = useState(false);
	const ref = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (touched || matchMedia("(prefers-reduced-motion: reduce)").matches)
			return;
		let frame = 0;
		let start = 0;
		let visible = false;
		const io = new IntersectionObserver(([e]) => {
			visible = e.isIntersecting;
		});
		if (ref.current) io.observe(ref.current);
		const tick = (t: number) => {
			start ||= t;
			if (visible) setPos(50 + 32 * Math.sin((t - start) / 1400));
			frame = requestAnimationFrame(tick);
		};
		frame = requestAnimationFrame(tick);
		return () => {
			cancelAnimationFrame(frame);
			io.disconnect();
		};
	}, [touched]);

	return (
		<div
			ref={ref}
			className="relative w-full aspect-[3/2] overflow-hidden rounded-[2px] border border-ink select-none"
		>
			{/* eslint-disable-next-line @next/next/no-img-element -- static demo pair, already sized */}
			{/* biome-ignore lint/performance/noImgElement: static demo pair, already sized */}
			<img
				src={after}
				alt={`After: ${alt}`}
				className="absolute inset-0 w-full h-full object-cover"
			/>
			{/* eslint-disable-next-line @next/next/no-img-element -- static demo pair, already sized */}
			{/* biome-ignore lint/performance/noImgElement: static demo pair, already sized */}
			<img
				src={before}
				alt={`Before: ${alt}`}
				className="absolute inset-0 w-full h-full object-cover"
				style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }}
			/>
			<div
				className="absolute inset-y-0 w-0.5 bg-paper shadow-[0_0_0_1px_var(--ink)]"
				style={{ left: `${pos}%` }}
				aria-hidden
			>
				<div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-9 rounded-full bg-paper border border-ink grid place-items-center text-ink text-sm">
					⇆
				</div>
			</div>
			<span className="absolute top-3 left-3 rounded bg-ink/80 px-2 py-0.5 font-mono text-[11px] text-paper">
				Before
			</span>
			<span className="absolute top-3 right-3 rounded bg-green px-2 py-0.5 font-mono text-[11px] text-paper">
				After
			</span>
			<input
				type="range"
				min={0}
				max={100}
				value={Math.round(pos)}
				aria-label="Compare before and after"
				onChange={(e) => {
					setTouched(true);
					setPos(Number(e.target.value));
				}}
				className="absolute inset-0 w-full h-full opacity-0 cursor-ew-resize focus-visible:opacity-0 peer"
			/>
			<div className="pointer-events-none absolute inset-0 rounded-[2px] peer-focus-visible:ring-2 peer-focus-visible:ring-green" />
		</div>
	);
}
