export interface EditInput {
	imageBuffer: Buffer;
	replacements: {
		from: string;
		to: string;
		x: number;
		y: number;
		width: number;
		height: number;
	}[];
}

export interface EditOutput {
	buffer: Buffer;
	provider: string;
	model: string;
}

export interface ImageEditor {
	edit(input: EditInput): Promise<EditOutput>;
}
