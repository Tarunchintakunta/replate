import { describe, it, expect } from 'vitest';
import { assertMagicBytes, processUpload, UnsupportedMimeTypeError, ImageTooLargeError } from './accept';
import sharp from 'sharp';

describe('accept', () => {
  it('rejects a text file renamed .png', async () => {
    const txtBuffer = Buffer.from('hello world');
    expect(() => assertMagicBytes(txtBuffer)).toThrow(UnsupportedMimeTypeError);
    await expect(processUpload(txtBuffer)).rejects.toThrow(UnsupportedMimeTypeError);
  });

  it('rejects an 8000px edge if pixel count is > 16M (e.g. 8000x8000 = 64M)', async () => {
    // Generate a 8000x8000 image
    const largeImg = await sharp({
      create: { width: 8000, height: 8000, channels: 4, background: { r: 255, g: 0, b: 0, alpha: 1 } }
    }).png().toBuffer();

    await expect(processUpload(largeImg)).rejects.toThrow(ImageTooLargeError);
  });

  it('accepts a real PNG and has no EXIF', async () => {
    // Create an image with EXIF metadata
    const pngBuffer = await sharp({
      create: { width: 100, height: 100, channels: 4, background: 'red' }
    }).withMetadata({
      orientation: 8
    }).png().toBuffer();
    
    expect(() => assertMagicBytes(pngBuffer)).not.toThrow();

    const result = await processUpload(pngBuffer);
    expect(result.width).toBe(100);
    expect(result.height).toBe(100);

    const outMetadata = await sharp(result.buffer).metadata();
    // sharp orientation is undefined if its stripped
    expect(outMetadata.orientation).toBeUndefined();
  });
});
