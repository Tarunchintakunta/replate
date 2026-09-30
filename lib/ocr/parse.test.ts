import { describe, it, expect } from 'vitest';
import { parseOcrOutput } from './parse';

describe('parseOcrOutput', () => {
  it('parses valid JSON and returns lines', () => {
    const json = JSON.stringify({
      lines: [{ text: "SALE", confidence: 0.9, x: 10, y: 12, width: 80, height: 24 }]
    });
    const lines = parseOcrOutput(json, 400, 400);
    expect(lines).toHaveLength(1);
    expect(lines[0].text).toBe('SALE');
  });

  it('filters out lines outside the image bounds', () => {
    const json = JSON.stringify({
      lines: [
        { text: "IN", confidence: 0.9, x: 10, y: 12, width: 80, height: 24 },
        { text: "OUT", confidence: 0.9, x: 350, y: 12, width: 80, height: 24 }
      ]
    });
    // The image width is 400. "OUT" ends at 350+80 = 430, which is > 400.
    const lines = parseOcrOutput(json, 400, 400);
    expect(lines).toHaveLength(1);
    expect(lines[0].text).toBe('IN');
  });

  it('rejects invalid JSON', () => {
    expect(() => parseOcrOutput('NOT JSON', 400, 400)).toThrow('Invalid JSON from OCR');
  });

  it('rejects schema variations (e.g. invalid confidence)', () => {
    const json = JSON.stringify({
      lines: [{ text: "SALE", confidence: 1.5, x: 10, y: 12, width: 80, height: 24 }]
    });
    expect(() => parseOcrOutput(json, 400, 400)).toThrow();
  });
});
