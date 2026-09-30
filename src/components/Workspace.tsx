"use client";

import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { ImageStage, type UploadedImage } from "./ImageStage";
import { LineList } from "./LineList";

export type Line = {
	id: string;
	text: string;
	replacement: string;
	x: number;
	y: number;
	width: number;
	height: number;
};

export function Workspace() {
	const [image, setImage] = useState<UploadedImage | null>(null);
	const [lines, setLines] = useState<Line[]>([]);
	const [selectedLineId, setSelectedLineId] = useState<string | null>(null);

	const handleDrawBox = (box: {
		x: number;
		y: number;
		width: number;
		height: number;
	}) => {
		const newLine: Line = {
			id: uuidv4(),
			text: "",
			replacement: "",
			...box,
		};
		setLines((prev) => [...prev, newLine]);
		setSelectedLineId(newLine.id);
	};

	return (
		<main className="flex-1 flex flex-col items-center justify-center p-4 lg:p-8">
			<div className="text-center mb-8">
				<p className="text-lg text-ink font-medium">
					Change the words. Keep the picture.
				</p>
			</div>

			<div className="w-full max-w-6xl mx-auto flex flex-col md:flex-row gap-6 flex-1 min-h-0">
				<div
					data-testid="left-col"
					className="w-full md:w-[60%] flex flex-col relative"
				>
					<ImageStage
						image={image}
						onImageUpload={setImage}
						lines={lines}
						selectedLineId={selectedLineId}
						onSelectLine={setSelectedLineId}
						onDrawBox={handleDrawBox}
					/>
				</div>

				<div
					data-testid="right-col"
					className="w-full md:w-[40%] flex flex-col gap-4"
				>
					<LineList
						image={image}
						lines={lines}
						setLines={setLines}
						selectedLineId={selectedLineId}
						onSelectLine={setSelectedLineId}
					/>

					<div className="border-t border-rule pt-4 flex flex-col gap-2">
						<button
							type="button"
							disabled
							className="bg-green text-paper py-2 px-4 rounded-md font-medium opacity-40 cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-green focus:ring-offset-2 focus:ring-offset-paper transition-shadow"
						>
							Generate
						</button>
						<div className="text-sm text-center text-ink opacity-70">
							10 credits
						</div>
					</div>
				</div>
			</div>
		</main>
	);
}
