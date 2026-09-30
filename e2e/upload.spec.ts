import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import sharp from 'sharp';

test('drop a generated PNG and see an img', async ({ page }) => {
  const pngBuffer = await sharp({
    create: { width: 400, height: 400, channels: 4, background: 'blue' }
  }).png().toBuffer();
  
  await fs.mkdir('temp', { recursive: true });
  const filePath = 'temp/test-upload.png';
  await fs.writeFile(filePath, pngBuffer);

  const errors: string[] = [];
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(msg.text());
    }
  });
  page.on('pageerror', err => {
    errors.push(err.message);
  });

  await page.goto('/');

  const fileInput = page.locator('input[type="file"]');
  await fileInput.setInputFiles(filePath);

  const img = page.locator('img[alt="Uploaded"]');
  await expect(img).toBeVisible();

  expect(errors.length).toBe(0);
});
