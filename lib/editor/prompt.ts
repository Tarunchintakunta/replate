export function buildPrompt(
	replacements: {
		from: string;
		to: string;
		x: number;
		y: number;
		width: number;
		height: number;
	}[],
): string {
	const lines = replacements.map((r, i) => {
		if (!r.to) {
			return `${i + 1}. Inside the box x=${r.x} y=${r.y} width=${r.width} height=${r.height}, remove the text in the box and reconstruct the background. No new letters.`;
		}
		return `${i + 1}. Inside the box x=${r.x} y=${r.y} width=${r.width} height=${r.height}, replace "${r.from}" with "${r.to}".`;
	});

	return `Edit this image. Change only the listed text. Keep font, color, size, perspective, lighting, and background. Do not alter anything else.

${lines.join("\n")}`;
}
