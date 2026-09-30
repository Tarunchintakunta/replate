import { signIn } from "./signin";
import { test, expect } from '@playwright/test';

test('shell empty state', async ({ page }) => {
  await signIn(page);

  await expect(page.getByRole('heading', { name: 'Replate' })).toBeVisible();
  await expect(page.getByText('Change the words. Keep the picture.')).toBeVisible();
  await expect(page.getByText('Drop a PNG, JPG, or WebP.')).toBeVisible();
  await expect(page.getByText('10').first()).toBeVisible();
});

test('layout stacks under 800px', async ({ page }) => {
  await signIn(page);
  await page.setViewportSize({ width: 390, height: 844 });
  
  const leftCol = page.getByTestId('left-col');
  const rightCol = page.getByTestId('right-col');
  
  const leftBox = await leftCol.boundingBox();
  const rightBox = await rightCol.boundingBox();
  
  expect(leftBox).not.toBeNull();
  expect(rightBox).not.toBeNull();
  if (leftBox && rightBox) {
    expect(rightBox.y).toBeGreaterThan(leftBox.y);
  }
});

test('layout is two columns at 1280px', async ({ page }) => {
  await signIn(page);
  await page.setViewportSize({ width: 1280, height: 800 });
  
  const leftCol = page.getByTestId('left-col');
  const rightCol = page.getByTestId('right-col');
  
  const leftBox = await leftCol.boundingBox();
  const rightBox = await rightCol.boundingBox();
  
  expect(leftBox).not.toBeNull();
  expect(rightBox).not.toBeNull();
  if (leftBox && rightBox) {
    expect(rightBox.x).toBeGreaterThan(leftBox.x);
    expect(Math.abs(rightBox.y - leftBox.y)).toBeLessThan(10);
  }
});
