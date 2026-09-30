import sharp from 'sharp';

export class UnsupportedMimeTypeError extends Error {
  constructor() {
    super('Use a PNG, JPG, or WebP.');
    this.name = 'UnsupportedMimeTypeError';
  }
}

export class FileSizeError extends Error {
  constructor() {
    super('File too large');
    this.name = 'FileSizeError';
  }
}

export class ImageTooLargeError extends Error {
  constructor() {
    super('Image dimensions or pixel count too large');
    this.name = 'ImageTooLargeError';
  }
}

export function assertMagicBytes(buffer: Buffer): void {
  // PNG: 89 50 4E 47
  if (buffer.length >= 4 && buffer[0] === 0x89 && buffer[1] === 0x50 && buffer[2] === 0x4E && buffer[3] === 0x47) {
    return;
  }
  // JPEG: FF D8 FF
  if (buffer.length >= 3 && buffer[0] === 0xff && buffer[1] === 0xd8 && buffer[2] === 0xff) {
    return;
  }
  // WebP: RIFF and WEBP
  if (buffer.length >= 12) {
    const isRiff = buffer[0] === 0x52 && buffer[1] === 0x49 && buffer[2] === 0x46 && buffer[3] === 0x46;
    const isWebp = buffer[8] === 0x57 && buffer[9] === 0x45 && buffer[10] === 0x42 && buffer[11] === 0x50;
    if (isRiff && isWebp) return;
  }
  
  throw new UnsupportedMimeTypeError();
}

const MAX_FILE_SIZE = 8 * 1024 * 1024;
const MAX_LONG_EDGE = 8192;
const MAX_PIXELS = 16_000_000;
const RESIZE_LONG_EDGE = 2048;

export interface AcceptedImage {
  buffer: Buffer;
  width: number;
  height: number;
}

export async function processUpload(buffer: Buffer): Promise<AcceptedImage> {
  if (buffer.length > MAX_FILE_SIZE) {
    throw new FileSizeError();
  }

  assertMagicBytes(buffer);

  let image = sharp(buffer);
  const metadata = await image.metadata();

  if (!metadata.width || !metadata.height) {
    throw new Error('Invalid image');
  }

  const longEdge = Math.max(metadata.width, metadata.height);
  const pixels = metadata.width * metadata.height;

  if (longEdge > MAX_LONG_EDGE || pixels > MAX_PIXELS) {
    throw new ImageTooLargeError();
  }

  if (longEdge > RESIZE_LONG_EDGE) {
    image = image.resize({
      width: metadata.width >= metadata.height ? RESIZE_LONG_EDGE : undefined,
      height: metadata.height > metadata.width ? RESIZE_LONG_EDGE : undefined,
      withoutEnlargement: true
    });
  }

  // Strip EXIF and re-encode to PNG
  const outBuffer = await image.rotate().png().toBuffer();
  const outMetadata = await sharp(outBuffer).metadata();
  
  return {
    buffer: outBuffer,
    width: outMetadata.width!,
    height: outMetadata.height!,
  };
}
