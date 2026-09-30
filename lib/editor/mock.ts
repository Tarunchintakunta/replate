import sharp from "sharp";
import type { EditInput, EditOutput, ImageEditor } from "./types";

export class MockEditor implements ImageEditor {
	async edit(input: EditInput): Promise<EditOutput> {
		const image = sharp(input.imageBuffer);
		const metadata = await image.metadata();
		const origWidth = metadata.width || 1024;
		const origHeight = metadata.height || 1024;

		let imgWidth = origWidth;
		let imgHeight = origHeight;

		const maxEdge = Math.max(origWidth, origHeight);
		let scale = 1;
		if (maxEdge > 1024) {
			scale = 1024 / maxEdge;
			imgWidth = Math.round(origWidth * scale);
			imgHeight = Math.round(origHeight * scale);
		}

		const resizedBuffer = await image
			.resize({ width: imgWidth, height: imgHeight, fit: "inside" })
			.png()
			.toBuffer();

		let svg = `<svg viewBox="0 0 ${imgWidth} ${imgHeight}" width="${imgWidth}" height="${imgHeight}" xmlns="http://www.w3.org/2000/svg">`;

		const { data: pixels, info } = await sharp(resizedBuffer)
			.toColourspace("srgb")
			.raw()
			.toBuffer({ resolveWithObject: true });
		const sampleAt = (px: number, py: number) => {
			const cx = Math.min(Math.max(px, 0), info.width - 1);
			const cy = Math.min(Math.max(py, 0), info.height - 1);
			const i = (cy * info.width + cx) * info.channels;
			return `rgb(${pixels[i]},${pixels[i + 1]},${pixels[i + 2]})`;
		};

		for (const r of input.replacements) {
			const x = Math.round(r.x * scale);
			const y = Math.round(r.y * scale);
			const w = Math.round(r.width * scale);
			const h = Math.round(r.height * scale);

			if (r.to) {
				svg += `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="white" stroke="black" stroke-width="1" />`;
				const fontSize = Math.max(12, h - 4);
				svg += `<text x="${x + 4}" y="${y + h - 4}" font-size="${fontSize}" fill="black" font-family="sans-serif">${r.to}</text>`;
			} else {
				svg += `<rect x="${x}" y="${y}" width="${w}" height="${h}" fill="${sampleAt(x - 1, y - 1)}" />`;
			}
		}
		svg += "</svg>";

		const finalBuffer = await sharp(resizedBuffer)
			.composite([{ input: Buffer.from(svg), top: 0, left: 0 }])
			// A removal on a flat background can be pixel-identical to the input; the tag
			// keeps the bytes different, as the spec requires.
			.withExif({ IFD0: { Software: "replate mock" } })
			.png()
			.toBuffer();

		return {
			buffer: finalBuffer,
			provider: "mock",
			model: "mock",
		};
	}
}
