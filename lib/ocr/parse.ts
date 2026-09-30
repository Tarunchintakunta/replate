import { z } from 'zod';

export const LineSchema = z.object({
  text: z.string().max(200),
  confidence: z.number().min(0).max(1),
  x: z.number().int().nonnegative(),
  y: z.number().int().nonnegative(),
  width: z.number().int().positive(),
  height: z.number().int().positive(),
});

export const OcrOutputSchema = z.object({
  lines: z.array(LineSchema),
});

export type ParsedLine = z.infer<typeof LineSchema>;
export type OcrOutput = z.infer<typeof OcrOutputSchema>;

export function parseOcrOutput(stdout: string, imageWidth: number, imageHeight: number): ParsedLine[] {
  let parsed: unknown;
  try {
    parsed = JSON.parse(stdout);
  } catch {
    throw new Error('Invalid JSON from OCR');
  }

  const result = OcrOutputSchema.parse(parsed);

  return result.lines.filter((line) => {
    // Drop lines whose box falls outside the image.
    // Since x and y are nonnegative based on Zod schema, we only need to check the right and bottom edges.
    if (line.x >= imageWidth || line.y >= imageHeight) {
      return false;
    }
    if (line.x + line.width > imageWidth || line.y + line.height > imageHeight) {
      return false;
    }
    return true;
  });
}
