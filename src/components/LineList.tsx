"use client";

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
			<h2 className="font-semibold text-ink mb-4">Lines</h2>

			{lines.length === 0 ? (
				<div className="text-sm text-ink opacity-70">
					Draw a box on the image to add a line.
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
										Box at x:{line.x} y:{line.y}
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
