"use client";

import { useRef, useState } from "react";
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
	const [showOriginal, setShowOriginal] = useState(false);
	const [detecting, setDetecting] = useState(false);
	const [detectError, setDetectError] = useState<string | null>(null);
	// The image a detection was started for; a slow answer for an older upload is dropped.
	const currentImageId = useRef<string | null>(null);

	const detect = async (img: UploadedImage) => {
		setDetecting(true);
		setDetectError(null);
		try {
			const res = await fetch(`/api/images/${img.id}/ocr`, { method: "POST" });
			const body = await res.json().catch(() => null);
			if (!res.ok) throw new Error(body?.error || "Failed to detect text");
			if (currentImageId.current !== img.id) return;
			const detected: Line[] = body.lines.map(
				(l: {
					id: string;
					text: string;
					x: number;
					y: number;
					width: number;
					height: number;
				}) => ({
					id: String(l.id),
					text: l.text,
					replacement: "",
					checked: false,
					detected: true,
					x: l.x,
					y: l.y,
					width: l.width,
					height: l.height,
				}),
			);
			// Detecting again must not undo the user's work: a line that comes back the
			// same keeps its replacement, and drawn boxes stay.
			const where = (l: Line) =>
				`${l.text}|${l.x}|${l.y}|${l.width}|${l.height}`;
			setLines((prev) => {
				const before = new Map(prev.map((l) => [where(l), l]));
				return [
					...detected.map((l) => {
						const old = before.get(where(l));
						return old
							? { ...l, replacement: old.replacement, checked: old.checked }
							: l;
					}),
					...prev.filter((l) => !l.detected),
				];
			});
		} catch (err) {
			if (currentImageId.current === img.id) {
				setDetectError((err as Error).message || "Failed to detect text");
			}
		} finally {
			if (currentImageId.current === img.id) setDetecting(false);
		}
	};

	const showResult = (id: string | null) => {
		setResultId(id);
		setShowOriginal(false);
	};

	const handleUpload = (img: UploadedImage) => {
		currentImageId.current = img.id;
		setImage(img);
		setLines([]);
		setSelectedLineId(null);
		showResult(null);
		void detect(img);
	};

	const openRecent = (generationId: string, img: UploadedImage) => {
		// The frame takes the picture's shape, so a result is only shown on its own picture.
		if (image?.id !== img.id) handleUpload(img);
		showResult(generationId);
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
		showResult(null);
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
						resultSrc={
							resultId && !showOriginal
								? `/api/generations/${resultId}/file`
								: null
						}
						lines={lines}
						selectedLineId={selectedLineId}
						onSelectLine={setSelectedLineId}
						onDrawBox={handleDrawBox}
					>
						<span className="opacity-70">
							{resultId && !showOriginal ? "Result" : "Original"}
						</span>
						{resultId && (
							<button
								type="button"
								onClick={() => setShowOriginal((v) => !v)}
								className="underline underline-offset-2 rounded focus:outline-none focus:ring-2 focus:ring-green"
							>
								{showOriginal ? "Show result" : "Show original"}
							</button>
						)}
					</ImageStage>
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
							showResult(null);
						}}
						detecting={detecting}
						detectError={detectError}
						onDetect={() => image && detect(image)}
					/>

					<GenerateBar
						imageId={image?.id ?? null}
						lines={lines}
						resultId={resultId}
						onResult={showResult}
						onOpenRecent={openRecent}
					/>
				</div>
			</div>
		</main>
	);
}
