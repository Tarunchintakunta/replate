"use client";

import { useState } from "react";
import { v4 as uuidv4 } from "uuid";
import { GenerateBar } from "./GenerateBar";
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
	/** Included in the next replace request. */
	checked: boolean;
	/** From OCR, so `id` is a real ocr_lines row. Drawn boxes are false. */
	detected: boolean;
};

export function Workspace() {
	const [image, setImage] = useState<UploadedImage | null>(null);
	const [lines, setLines] = useState<Line[]>([]);
	const [selectedLineId, setSelectedLineId] = useState<string | null>(null);
	const [resultId, setResultId] = useState<string | null>(null);

	const handleUpload = (img: UploadedImage) => {
		setImage(img);
		setLines([]);
		setSelectedLineId(null);
		setResultId(null);
	};

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
			checked: true,
			detected: false,
			...box,
		};
		setLines((prev) => [...prev, newLine]);
		setSelectedLineId(newLine.id);
		setResultId(null);
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
						onImageUpload={handleUpload}
						resultSrc={resultId ? `/api/generations/${resultId}/file` : null}
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
						onSelectLine={(id) => {
							setSelectedLineId(id);
							setResultId(null);
						}}
					/>

					<GenerateBar
						imageId={image?.id ?? null}
						lines={lines}
						resultId={resultId}
						onResult={setResultId}
					/>
				</div>
			</div>
		</main>
	);
}
