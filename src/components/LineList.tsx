"use client";

import { useEffect, useRef } from "react";
import type { UploadedImage } from "./ImageStage";
import type { Line } from "./Workspace";

interface LineListProps {
	image: UploadedImage | null;
	lines: Line[];
	setLines: React.Dispatch<React.SetStateAction<Line[]>>;
	selectedLineId: string | null;
	onSelectLine: (id: string | null) => void;
	detecting: boolean;
	detectError: string | null;
	onDetect: () => void;
}

export function LineList({
	image,
	lines,
	setLines,
	selectedLineId,
	onSelectLine,
	detecting,
	detectError,
	onDetect,
}: LineListProps) {
	const listRef = useRef<HTMLDivElement>(null);

	// A box clicked on the picture brings its row into view.
	useEffect(() => {
		if (!selectedLineId) return;
		listRef.current
			?.querySelector(`[data-line="${selectedLineId}"]`)
			?.scrollIntoView({ block: "nearest" });
	}, [selectedLineId]);

	if (!image) {
		return (
			<div className="flex-1 border border-rule rounded-md p-4 bg-paper flex flex-col">
				<h2 className="font-semibold text-ink mb-4">Lines</h2>
				<div className="text-sm text-ink opacity-70">No image uploaded.</div>
			</div>
		);
	}

	const chosen = lines.filter((l) => l.checked).length;

	return (
		<div
			ref={listRef}
			className="flex-1 border border-rule rounded-md p-4 bg-paper flex flex-col min-h-[300px] max-h-[600px] overflow-auto"
		>
			<div className="flex items-center justify-between mb-4">
				<h2 className="font-semibold text-ink">
					Lines
					{lines.length > 0 && (
						<span className="ml-2 font-normal text-sm opacity-70">
							{chosen} of {lines.length} chosen
						</span>
					)}
				</h2>
				<button
					type="button"
					onClick={onDetect}
					disabled={detecting}
					className="text-xs bg-wash border border-rule hover:bg-paper px-2 py-1 rounded text-ink transition-colors disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-green"
				>
					{detecting ? "Detecting..." : "Detect Text"}
				</button>
			</div>

			{detectError && (
				<div className="text-sm text-danger mb-3">{detectError}</div>
			)}

			{lines.length === 0 ? (
				<div className="text-sm text-ink opacity-70">
					{detecting
						? "Reading the picture…"
						: "Draw a box on the image to add a line, or click Detect Text."}
				</div>
			) : (
				<div className="flex flex-col gap-3">
					{lines.map((line) => {
						const isSelected = selectedLineId === line.id;
						return (
							// biome-ignore lint/a11y/noStaticElementInteractions: Custom list item
							// biome-ignore lint/a11y/useKeyWithClickEvents: Custom list item
							<div
								key={line.id}
								data-line={line.id}
								className={`flex flex-col gap-2 p-3 rounded-md border transition-colors ${
									isSelected ? "bg-wash border-green" : "bg-paper border-rule"
								}`}
								onClick={() => onSelectLine(line.id)}
							>
								<div className="flex items-start gap-2">
									<input
										type="checkbox"
										checked={line.checked}
										aria-label={`Replace ${line.text ? `"${line.text}"` : "drawn box"}`}
										onClick={(e) => e.stopPropagation()}
										onChange={() =>
											setLines((prev) =>
												prev.map((l) =>
													l.id === line.id ? { ...l, checked: !l.checked } : l,
												),
											)
										}
										className="w-4 h-4 mt-0.5 shrink-0 cursor-pointer accent-green"
									/>
									<span className="text-sm font-medium text-ink break-words min-w-0">
										{line.text
											? `"${line.text}"`
											: `Box at x:${line.x} y:${line.y}`}
									</span>
								</div>

								<div className="flex flex-col gap-1">
									<label
										className="text-xs font-medium text-ink opacity-70"
										htmlFor={`replace-${line.id}`}
									>
										Replacement
									</label>
									<input
										id={`replace-${line.id}`}
										type="text"
										value={line.replacement || ""}
										maxLength={200}
										onChange={(e) => {
											setLines((prev) =>
												prev.map((l) =>
													l.id === line.id
														? {
																...l,
																replacement: e.target.value,
																checked: true,
															}
														: l,
												),
											);
										}}
										placeholder="Empty means remove"
										className="border border-rule rounded px-2 py-1.5 text-sm bg-paper text-ink focus:outline-none focus:border-green focus:ring-1 focus:ring-green"
										onClick={(e) => e.stopPropagation()}
									/>
								</div>
							</div>
						);
					})}
				</div>
			)}
		</div>
	);
}
