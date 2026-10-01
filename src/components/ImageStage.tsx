"use client";

import {
	type ChangeEvent,
	type DragEvent,
	type PointerEvent,
	type ReactNode,
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
	/** Shown under the picture, beside the control that swaps it for another. */
	children?: ReactNode;
}

const ACCEPT = "image/png,image/jpeg,image/webp";

export function ImageStage({
	image,
	onImageUpload,
	resultSrc,
	lines,
	selectedLineId,
	onSelectLine,
	onDrawBox,
	children,
}: ImageStageProps) {
	const [uploading, setUploading] = useState(false);
	const [error, setError] = useState<string | null>(null);
	const imgRef = useRef<HTMLImageElement>(null);

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
		// Let the same file be chosen again.
		e.target.value = "";
	};

	const getPointerPos = (e: PointerEvent) => {
		if (!imgRef.current || !image) return null;
		// Map from the rendered <img> rect (not the frame, which carries the border)
		// into image pixels, clamped so boxes never leave the image.
		const rect = imgRef.current.getBoundingClientRect();
		const x = ((e.clientX - rect.left) / rect.width) * image.width;
		const y = ((e.clientY - rect.top) / rect.height) * image.height;
		return {
			x: Math.round(Math.min(Math.max(x, 0), image.width)),
			y: Math.round(Math.min(Math.max(y, 0), image.height)),
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
				className="flex-1 min-h-[220px] border border-rule rounded-md border-dashed bg-wash flex flex-col items-center justify-center p-6 focus-within:ring-2 focus-within:ring-green focus-within:ring-offset-2 focus-within:ring-offset-paper transition-shadow"
			>
				<label className="cursor-pointer text-center flex flex-col items-center w-full h-full justify-center">
					<span className="text-ink font-medium">
						{uploading ? "Uploading..." : "Drop a PNG, JPG, or WebP."}
					</span>
					{!uploading && (
						<span className="text-sm text-ink opacity-70 mt-1">
							Or click to choose a file. Up to 8 MB.
						</span>
					)}
					{error && <span className="text-danger text-sm mt-2">{error}</span>}
					<input
						type="file"
						accept={ACCEPT}
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
		// biome-ignore lint/a11y/noStaticElementInteractions: drag drop wrapper
		<div
			className="w-full flex flex-col items-center gap-2"
			onDragOver={(e) => e.preventDefault()}
			onDrop={onDrop}
		>
			{/* Frame is exactly the image's aspect ratio, capped at 75vh tall, so the
			    <img>, the SVG overlay and pointer mapping all share one rect. */}
			<div
				className="relative border border-ink rounded-[2px] overflow-hidden touch-none select-none cursor-crosshair"
				style={{
					aspectRatio: `${image.width} / ${image.height}`,
					width: `min(100%, calc(75vh * ${image.width / image.height}))`,
				}}
				onPointerDown={onPointerDown}
				onPointerMove={onPointerMove}
				onPointerUp={onPointerUp}
				onPointerCancel={onPointerUp}
			>
				{/* eslint-disable-next-line @next/next/no-img-element */}
				<img
					src={resultSrc ?? `/api/images/${image.id}/file`}
					alt={resultSrc ? "Result" : "Uploaded"}
					ref={imgRef}
					draggable={false}
					className="block w-full h-full pointer-events-none"
				/>
				{!resultSrc && (
					<svg
						aria-label="Image annotation layer"
						role="img"
						className="absolute inset-0 w-full h-full pointer-events-none"
						viewBox={`0 0 ${image.width} ${image.height}`}
						preserveAspectRatio="none"
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
			<div className="w-full flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-sm text-ink">
				<div className="flex items-center gap-4">{children}</div>
				<label className="cursor-pointer underline underline-offset-2 rounded focus-within:ring-2 focus-within:ring-green">
					{uploading ? "Uploading..." : "Choose another picture"}
					<input
						type="file"
						accept={ACCEPT}
						onChange={onChange}
						className="sr-only"
						disabled={uploading}
					/>
				</label>
			</div>
			{error && <p className="w-full text-sm text-danger">{error}</p>}
		</div>
	);
}
