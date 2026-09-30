import { describe, it, expect } from 'vitest';
import { runOcr } from './run';
import path from 'node:path';
import sharp from 'sharp';
import fs from 'node:fs/promises';

describe('runOcr sidecar', () => {
  it('returns lines from the script in rapid mode', async () => {
    if (!process.env.RUN_OCR) {
      console.log('Skipping sidecar test since RUN_OCR=1 is not set');
      return;
    }

    process.env.OCR_MODE = 'rapid';
    
    const testImgPath = path.resolve('temp-sidecar-test.png');
    await sharp({
      create: { width: 400, height: 200, channels: 4, background: { r: 255, g: 255, b: 255, alpha: 1 } }
    })
    .composite([
      {
        input: Buffer.from(
          `<svg width="400" height="200">
            <text x="50" y="100" font-family="sans-serif" font-size="48" fill="black">SALE</text>
           </svg>`
        ),
        top: 0, left: 0
      }
    ])
    .png()
    .toFile(testImgPath);
    
    try {
      const lines = await runOcr(testImgPath, 400, 200);
      expect(lines.length).toBeGreaterThan(0);
      
      const foundSale = lines.some(l => l.text.includes('SALE'));
      expect(foundSale).toBe(true);
    } finally {
      await fs.unlink(testImgPath).catch(() => {});
    }
  }, 15000); // give it up to 15s since initial model load in sidecar can take time
});
