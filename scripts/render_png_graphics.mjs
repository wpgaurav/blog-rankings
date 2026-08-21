#!/usr/bin/env node
// Gatilab Blog Rankings PNG renderer, adapted from png-graphics/scripts/render.mjs.

import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';

const require = createRequire(import.meta.url);
const { chromium } = require('playwright');

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');
const sourceDir = path.join(root, 'graphics', 'png', 'source');
const outputRoot = path.join(root, 'assets', 'png-graphics');
const pictureRoot = path.join(
  process.env.HOME,
  'Pictures',
  new Date().toISOString().slice(0, 10),
  'gatilab.com',
  'blog-rankings'
);

const sourceFiles = (await fs.readdir(sourceDir))
  .filter((name) => name.endsWith('.html'))
  .sort();

const outputFor = (stem) => {
  if (stem.startsWith('category-')) return path.join(outputRoot, 'categories', `${stem.slice(9)}.png`);
  if (stem.startsWith('rank-')) return path.join(outputRoot, 'rank-badges', `${stem}.png`);
  return path.join(outputRoot, `${stem}.png`);
};

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1080, height: 800 },
  deviceScaleFactor: 2,
});
const page = await context.newPage();

for (const filename of sourceFiles) {
  const stem = path.basename(filename, '.html');
  const sourcePath = path.join(sourceDir, filename);
  const outputPath = outputFor(stem);
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await page.goto(`file://${sourcePath}`, { waitUntil: 'networkidle' });
  await page.evaluate(() => document.fonts.ready);
  await page.waitForTimeout(700);

  const audit = await page.evaluate(() => {
    const main = document.querySelector('main');
    if (!main) throw new Error('Missing <main> element');
    const minSize = Number(main.dataset.minFontSize || 11);
    const minPadding = Number(main.dataset.minTextPadding || 8);
    const mainRect = main.getBoundingClientRect();
    const failures = [];

    for (const element of main.querySelectorAll('*')) {
      const text = element.textContent.trim();
      const style = getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      if (!text || style.display === 'none' || style.visibility === 'hidden' || !rect.width || !rect.height) continue;
      const directText = [...element.childNodes].some(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim()
      );
      if (!directText) continue;
      const size = parseFloat(style.fontSize);
      if (size < minSize - 0.1) failures.push(`${element.tagName} below ${minSize}px: ${size}px`);
      if (element.scrollWidth > element.clientWidth + 1 || element.scrollHeight > element.clientHeight + 1) {
        failures.push(`${element.tagName} overflows: ${text.slice(0, 70)}`);
      }
      if (
        rect.left < mainRect.left - 1 || rect.right > mainRect.right + 1 ||
        rect.top < mainRect.top - 1 || rect.bottom > mainRect.bottom + 1
      ) failures.push(`${element.tagName} escapes canvas: ${text.slice(0, 70)}`);
    }

    const edgeText = [...main.querySelectorAll('h1,h2,h3,p,li,span')].filter((element) => {
      const rect = element.getBoundingClientRect();
      const style = getComputedStyle(element);
      return element.textContent.trim() && style.position !== 'absolute' && rect.width && rect.height;
    });
    for (const element of edgeText) {
      const rect = element.getBoundingClientRect();
      if (
        rect.left - mainRect.left < minPadding - 0.5 || mainRect.right - rect.right < minPadding - 0.5 ||
        rect.top - mainRect.top < minPadding - 0.5 || mainRect.bottom - rect.bottom < minPadding - 0.5
      ) failures.push(`${element.tagName} violates ${minPadding}px canvas inset: ${element.textContent.trim().slice(0, 70)}`);
    }
    return { failures, minSize, minPadding };
  });

  if (audit.failures.length) {
    throw new Error(`${stem}: PNG audit failed:\n${audit.failures.join('\n')}`);
  }

  let box = await page.locator('main').boundingBox();
  await page.setViewportSize({
    width: Math.max(1080, Math.ceil(box.width + box.x + 40)),
    height: Math.max(800, Math.ceil(box.height + box.y + 40)),
  });
  await page.waitForTimeout(200);
  box = await page.locator('main').boundingBox();
  await page.screenshot({
    path: outputPath,
    omitBackground: stem.startsWith('rank-'),
    clip: {
      x: Math.round(box.x),
      y: Math.round(box.y),
      width: Math.round(box.width),
      height: Math.round(box.height),
    },
  });
  const picturePath = path.join(pictureRoot, path.relative(outputRoot, outputPath));
  await fs.mkdir(path.dirname(picturePath), { recursive: true });
  await fs.copyFile(outputPath, picturePath);
  console.log(`${stem} -> ${Math.round(box.width * 2)} x ${Math.round(box.height * 2)} px`);
}

await browser.close();
