import { createRequire } from 'node:module';
import { mkdir } from 'node:fs/promises';
import path from 'node:path';

const require = createRequire('C:/Users/liujunqing/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright/package.json');
const { chromium } = require('playwright');

const baseUrl = 'https://evo-graph.vercel.app';
const outDir = path.resolve('docs', 'evograph-demo-assets');

const pages = [
  { name: '01-graph-explorer', url: `${baseUrl}/`, waitFor: 'text=Knowledge Graph Explorer' },
  { name: '02-query-console', url: `${baseUrl}/query`, waitFor: 'text=Query Console' },
  { name: '03-document-ingestion', url: `${baseUrl}/documents`, waitFor: 'text=Document' },
  { name: '04-conflict-dashboard', url: `${baseUrl}/conflicts`, waitFor: 'text=Knowledge Conflicts' },
  { name: '05-timeline', url: `${baseUrl}/timeline`, waitFor: 'text=Timeline' },
];

await mkdir(outDir, { recursive: true });

const browser = await chromium.launch({ headless: true });
const context = await browser.newContext({
  viewport: { width: 1440, height: 960 },
  deviceScaleFactor: 1,
});

for (const item of pages) {
  const page = await context.newPage();
  await page.goto(item.url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForSelector(item.waitFor, { timeout: 30000 }).catch(() => {});
  await page.waitForTimeout(1200);
  await page.screenshot({
    path: path.join(outDir, `${item.name}.png`),
    fullPage: true,
  });
  await page.close();
}

await browser.close();
console.log(`Saved ${pages.length} screenshots to ${outDir}`);
