"use client";

import { useState } from "react";
import type { UploadedImage } from "./ImageStage";
import type { Line } from "./Workspace";

interface LineListProps {
	image: UploadedImage | null;
	lines: Line[];
	setLines: React.Dispatch<React.SetStateAction<Line[]>>;
	selectedLineId: string | null;
	onSelectLine: (id: string | null) => void;
}

export function LineList({
	image,
	lines,
	setLines,
	selectedLineId,
	onSelectLine,
}: LineListProps) {
	const [detecting, setDetecting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleDetect = async () => {
		if (!image) return;
		setDetecting(true);
		setError(null);
		try {
			const res = await fetch(`/api/images/${image.id}/ocr`, {
				method: "POST",
			});
			if (!res.ok) {
				throw new Error("Failed to detect text");
			}
			const data = await res.json();
			setLines(
				data.lines.map(
					(l: {
						id: string;
						text: string;
						replacedWith: string | null;
						x: number;
						y: number;
						width: number;
						height: number;
					}) => ({
						id: String(l.id),
						text: l.text,
						replacement: l.replacedWith || "",
						x: l.x,
						y: l.y,
						width: l.width,
						height: l.height,
					}),
				),
			);
			onSelectLine(null);
		} catch (err) {
			const error = err as Error;
			setError(error.message || "Something went wrong");
		} finally {
			setDetecting(false);
		}
	};

	if (!image) {
		return (
			<div className="flex-1 border border-rule rounded-md p-4 bg-paper flex flex-col">
				<h2 className="font-semibold text-ink mb-4">Lines</h2>
				<div className="text-sm text-ink opacity-70">No image uploaded.</div>
			</div>
		);
	}

	return (
		<div className="flex-1 border border-rule rounded-md p-4 bg-paper flex flex-col min-h-[300px] max-h-[600px] overflow-auto">
			<div className="flex items-center justify-between mb-4">
				<h2 className="font-semibold text-ink">Lines</h2>
				<button
					type="button"
					onClick={handleDetect}
					disabled={detecting}
					className="text-xs bg-wash border border-rule hover:bg-paper px-2 py-1 rounded text-ink transition-colors disabled:opacity-50"
				>
					{detecting ? "Detecting..." : "Detect Text"}
				</button>
			</div>

			{error && <div className="text-sm text-danger mb-3">{error}</div>}

			{lines.length === 0 ? (
				<div className="text-sm text-ink opacity-70">
					Draw a box on the image to add a line, or click Detect Text.
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
								className={`flex flex-col gap-2 p-3 rounded-md border transition-colors ${
									isSelected
										? "bg-wash border-green"
										: "bg-paper border-rule opacity-80"
								}`}
								onClick={() => onSelectLine(line.id)}
							>
								<div className="flex items-center gap-2">
									<input
										type="checkbox"
										checked={isSelected}
										onChange={() => onSelectLine(isSelected ? null : line.id)}
										className="w-4 h-4 cursor-pointer"
									/>
									<span className="text-sm font-medium text-ink">
										{line.text
											? `"${line.text}"`
											: `Box at x:${line.x} y:${line.y}`}
									</span>
								</div>

								<div className="flex flex-col gap-1 mt-1">
									<label
										className="text-xs font-medium text-ink"
										htmlFor={`replace-${line.id}`}
									>
										Replacement
									</label>
									<input
										id={`replace-${line.id}`}
										type="text"
										value={line.replacement || ""}
										onChange={(e) => {
											setLines((prev) =>
												prev.map((l) =>
													l.id === line.id
														? { ...l, replacement: e.target.value }
														: l,
												),
											);
										}}
										placeholder="Empty means remove"
										className="border border-rule rounded px-2 py-1 text-sm bg-paper text-ink focus:outline-none focus:border-green"
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
