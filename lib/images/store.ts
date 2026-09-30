import fs from 'node:fs/promises';
import path from 'node:path';

export function originalKey(imageId: string): string {
  return `originals/${imageId}.png`;
}

export function generationKey(generationId: string): string {
  return `generations/${generationId}.png`;
}

function getStorageBase(): string {
  // Use config or env if needed, but default to 'storage'
  return path.resolve(process.env.STORAGE_PATH || 'storage');
}

export async function writePng(key: string, data: Buffer): Promise<void> {
  if (key.includes('..')) {
    throw new Error('Path traversal detected');
  }

  const base = getStorageBase();
  const fullPath = path.resolve(base, key);

  if (!fullPath.startsWith(base)) {
    throw new Error('Path traversal detected');
  }

  await fs.mkdir(path.dirname(fullPath), { recursive: true });
  await fs.writeFile(fullPath, data);
}

export async function readPng(key: string): Promise<Buffer> {
  if (key.includes('..')) {
    throw new Error('Path traversal detected');
  }

  const base = getStorageBase();
  const fullPath = path.resolve(base, key);

  if (!fullPath.startsWith(base)) {
    throw new Error('Path traversal detected');
  }

  return fs.readFile(fullPath);
}
