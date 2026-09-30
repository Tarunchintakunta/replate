import { spawn } from 'node:child_process';
import path from 'node:path';
import { type ParsedLine, parseOcrOutput } from './parse';

export async function runOcr(imagePath: string, imageWidth: number, imageHeight: number): Promise<ParsedLine[]> {
  const mode = process.env.OCR_MODE || 'fixture';
  
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

  return new Promise((resolve, reject) => {
    // turbopackIgnore: the venv is spawned at runtime and its python symlink leaves the repo.
    const pythonPath = path.join(/* turbopackIgnore: true */ process.cwd(), 'services/ocr/.venv/bin/python');
    const scriptPath = path.join(/* turbopackIgnore: true */ process.cwd(), 'services/ocr/ocr.py');
    
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
