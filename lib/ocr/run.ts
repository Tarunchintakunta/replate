import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { type ParsedLine, parseOcrOutput } from './parse';

export async function runOcr(imagePath: string, imageWidth: number, imageHeight: number): Promise<ParsedLine[]> {
  const mode = process.env.OCR_MODE || 'rapid';

  if (mode === 'fixture') {
    return [
      {
        text: 'SALE',
        confidence: 1,
        x: 8,
        y: 8,
        width: 48,
        height: 16
      }
    ];
  }

  // turbopackIgnore: the venv is spawned at runtime and its python symlink leaves the repo.
  const pythonPath = path.join(/* turbopackIgnore: true */ process.cwd(), 'services/ocr/.venv/bin/python');
  const scriptPath = path.join(/* turbopackIgnore: true */ process.cwd(), 'services/ocr/ocr.py');
  if (!existsSync(pythonPath)) {
    throw new Error(
      'OCR is not installed. Run: python3 -m venv services/ocr/.venv && services/ocr/.venv/bin/pip install -r services/ocr/requirements.txt',
    );
  }

  return new Promise((resolve, reject) => {
    const child = spawn(pythonPath, [scriptPath, imagePath], {
      timeout: 10000, // 10 second kill
    });
    
    let stdout = '';
    let stderr = '';
    
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    
    child.on('error', (err) => {
      reject(new Error(`Failed to start OCR process: ${err.message}`));
    });
    
    child.on('close', (code, signal) => {
      if (code !== 0) {
        if (signal === 'SIGTERM') {
          // spawn with timeout sends SIGTERM
          reject(new Error('OCR process timed out'));
        } else {
          reject(new Error(`OCR failed (exit ${code}): ${stderr}`));
        }
        return;
      }
      
      try {
        const lines = parseOcrOutput(stdout, imageWidth, imageHeight);
        resolve(lines);
      } catch (err) {
        reject(err);
      }
    });
  });
}
