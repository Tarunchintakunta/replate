"use client";

import {
	type ChangeEvent,
	type DragEvent,
	type PointerEvent,
	useRef,
	useState,
} from "react";
import type { Line } from "./Workspace";

export type UploadedImage = {
	id: string;
	width: number;
	height: number;
};

interface ImageStageProps {
	image: UploadedImage | null;
	onImageUpload: (img: UploadedImage) => void;
	/** When set, the preview shows this generated PNG instead of the original. */
	resultSrc: string | null;
	lines: Line[];
	selectedLineId: string | null;
	onSelectLine: (id: string | null) => void;
	onDrawBox: (box: {
		x: number;
		y: number;
		width: number;
		height: number;
	}) => void;
}

export function ImageStage({
	image,
	onImageUpload,
	resultSrc,
	lines,
	selectedLineId,
	onSelectLine,
	onDrawBox,
}: ImageStageProps) {
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const imgContainerRef = useRef<HTMLDivElement>(null);

	const [drawing, setDrawing] = useState(false);
	const [startX, setStartX] = useState(0);
	const [startY, setStartY] = useState(0);
	const [currentX, setCurrentX] = useState(0);
	const [currentY, setCurrentY] = useState(0);

	const handleFile = async (file: File) => {
		setUploading(true);
		setError(null);
		try {
			const fd = new FormData();
			fd.append("file", file);
			const res = await fetch("/api/images", { method: "POST", body: fd });
			if (!res.ok) {
				const body = await res.json();
				throw new Error(body.error || "Upload failed");
			}
			const data = await res.json();
			onImageUpload(data);
		} catch (err) {
			const error = err as Error;
			setError(error.message);
		} finally {
			setUploading(false);
		}
	};

	const onDrop = (e: DragEvent<HTMLDivElement>) => {
		e.preventDefault();
		if (e.dataTransfer.files?.[0]) handleFile(e.dataTransfer.files[0]);
	};

	const onChange = (e: ChangeEvent<HTMLInputElement>) => {
		if (e.target.files?.[0]) handleFile(e.target.files[0]);
	};

	const getPointerPos = (e: PointerEvent) => {
		if (!imgContainerRef.current || !image) return null;
		const rect = imgContainerRef.current.getBoundingClientRect();
		const scaleX = image.width / rect.width;
		const scaleY = image.height / rect.height;
		return {
			x: Math.round((e.clientX - rect.left) * scaleX),
			y: Math.round((e.clientY - rect.top) * scaleY),
		};
	};

	const onPointerDown = (e: PointerEvent) => {
		const pos = getPointerPos(e);
		if (!pos) return;
		e.currentTarget.setPointerCapture(e.pointerId);
		setDrawing(true);
		setStartX(pos.x);
		setStartY(pos.y);
		setCurrentX(pos.x);
		setCurrentY(pos.y);
		onSelectLine(null);
	};

	const onPointerMove = (e: PointerEvent) => {
		if (!drawing) return;
		const pos = getPointerPos(e);
		if (!pos) return;
		setCurrentX(pos.x);
		setCurrentY(pos.y);
	};

	const onPointerUp = (e: PointerEvent) => {
		if (!drawing) return;
		e.currentTarget.releasePointerCapture(e.pointerId);
		setDrawing(false);
		const pos = getPointerPos(e);
		if (!pos) return;

		const endX = pos.x;
		const endY = pos.y;
		const x = Math.min(startX, endX);
		const y = Math.min(startY, endY);
		const width = Math.abs(endX - startX);
		const height = Math.abs(endY - startY);

		if (width >= 8 && height >= 8) {
			onDrawBox({ x, y, width, height });
		}
	};

	if (!image) {
		return (
			// biome-ignore lint/a11y/noStaticElementInteractions: drag drop wrapper
			<div
				onDragOver={(e) => e.preventDefault()}
				onDrop={onDrop}
				className="flex-1 border border-rule rounded-md border-dashed bg-wash flex flex-col items-center justify-center p-6 focus-within:ring-2 focus-within:ring-green focus-within:ring-offset-2 focus-within:ring-offset-paper transition-shadow"
			>
				<label className="cursor-pointer text-center flex flex-col items-center w-full h-full justify-center">
					<span className="text-ink font-medium">
						{uploading ? "Uploading..." : "Drop a PNG, JPG, or WebP."}
					</span>
					{error && <span className="text-danger text-sm mt-2">{error}</span>}
					<input
						type="file"
						onChange={onChange}
						className="sr-only"
						aria-label="Drop a PNG, JPG, or WebP."
						disabled={uploading}
					/>
				</label>
			</div>
		);
	}

	const displayDrawX = Math.min(startX, currentX);
	const displayDrawY = Math.min(startY, currentY);
	const displayDrawW = Math.abs(currentX - startX);
	const displayDrawH = Math.abs(currentY - startY);

	return (
		<div className="flex-1 rounded-md bg-wash border border-rule flex items-center justify-center overflow-hidden relative">
			<div
				ref={imgContainerRef}
				className="relative shadow-sm max-w-full max-h-full touch-none select-none cursor-crosshair"
				style={{ aspectRatio: `${image.width} / ${image.height}` }}
				onPointerDown={onPointerDown}
				onPointerMove={onPointerMove}
				onPointerUp={onPointerUp}
				onPointerCancel={onPointerUp}
			>
				{/* eslint-disable-next-line @next/next/no-img-element */}
				<img
					src={resultSrc ?? `/api/images/${image.id}/file`}
					alt={resultSrc ? "Result" : "Uploaded"}
					draggable={false}
					className="w-full h-full object-contain pointer-events-none"
				/>
				{!resultSrc && (
					<svg
						aria-label="Image annotation layer"
						role="img"
						className="absolute inset-0 w-full h-full pointer-events-none"
						viewBox={`0 0 ${image.width} ${image.height}`}
						preserveAspectRatio="xMidYMid meet"
					>
						{lines.map((line) => {
							const isSelected = line.id === selectedLineId;
							return (
								<rect
									key={line.id}
									x={line.x}
									y={line.y}
									width={line.width}
									height={line.height}
									fill="rgba(255,255,255,0.2)"
									stroke={
										isSelected ? "var(--color-green)" : "var(--color-ink)"
									}
									strokeWidth={isSelected ? 2 : 1}
									vectorEffect="non-scaling-stroke"
									className="pointer-events-auto cursor-pointer transition-colors"
									onPointerDown={(e) => {
										e.stopPropagation();
										onSelectLine(line.id);
									}}
								/>
							);
						})}
						{drawing && displayDrawW > 0 && displayDrawH > 0 && (
							<rect
								x={displayDrawX}
								y={displayDrawY}
								width={displayDrawW}
								height={displayDrawH}
								fill="rgba(14, 107, 82, 0.1)"
								stroke="var(--color-green)"
								strokeWidth={2}
								vectorEffect="non-scaling-stroke"
							/>
						)}
					</svg>
				)}
			</div>
		</div>
	);
}
