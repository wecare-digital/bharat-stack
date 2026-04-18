#!/usr/bin/env node
/**
 * Generate sitemap.xml for stack.wecare.digital
 * Scans the out/ directory for HTML files and generates a sitemap.
 * Run after `next build && next export` or `npm run build`.
 *
 * Usage: node scripts/generate-sitemap.js
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const SITE_URL = 'https://stack.wecare.digital';
const OUT_DIR = path.join(__dirname, '..', 'out');
const OUTPUT_FILE = path.join(OUT_DIR, 'sitemap.xml');

// Pages that should NOT be in the sitemap (internal/auth-protected)
const EXCLUDE = [
  '/404', '/_not-found', '/.well-known',
];

function findHtmlFiles(dir, base = '') {
  const urls = [];
  if (!fs.existsSync(dir)) return urls;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    const urlPath = base + '/' + entry.name;

    if (entry.isDirectory()) {
      // Skip node_modules, _next, etc.
      if (entry.name.startsWith('_') || entry.name.startsWith('.') || entry.name === 'node_modules') continue;
      urls.push(...findHtmlFiles(fullPath, urlPath));
    } else if (entry.name === 'index.html') {
      const pagePath = base || '/';
      // Check exclusions
      if (!EXCLUDE.some(ex => pagePath.startsWith(ex))) {
        urls.push(pagePath + '/');
      }
    }
  }
  return urls;
}

function generateSitemap(urls) {
  const today = new Date().toISOString().split('T')[0];
  const entries = urls.map(url => `  <url>
    <loc>${SITE_URL}${url}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>${url === '/' ? '1.0' : '0.7'}</priority>
  </url>`).join('\n');

  return `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${entries}
</urlset>`;
}

// Run
const urls = findHtmlFiles(OUT_DIR);
console.log(`Found ${urls.length} pages in out/`);
urls.forEach(u => console.log(`  ${u}`));

const sitemap = generateSitemap(urls);
fs.writeFileSync(OUTPUT_FILE, sitemap, 'utf-8');
console.log(`\nSitemap written to: ${OUTPUT_FILE}`);
console.log(`Submit to Google: ${SITE_URL}/sitemap.xml`);
