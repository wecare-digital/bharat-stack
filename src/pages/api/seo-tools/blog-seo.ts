/**
 * API Route: /api/seo-tools/blog-seo
 * Triggers the Python SEO master update script for blog + product SEO.
 * Runs seo_master_update_v2.py steps 1-3 (products, blog, FAQ).
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import { exec } from 'child_process';
import path from 'path';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });

  const scriptPath = path.resolve(process.cwd(), '..', 'seo-crawler', 'scripts', 'seo_master_update_v2.py');

  try {
    const result = await new Promise<string>((resolve, reject) => {
      exec(`python -u "${scriptPath}"`, { timeout: 300000, cwd: path.dirname(scriptPath) }, (err, stdout, stderr) => {
        if (err && !stdout) return reject(new Error(stderr || err.message));
        resolve(stdout + (stderr || ''));
      });
    });

    // Parse results from the output
    const productsMatch = result.match(/Products=(\d+)/);
    const blogMatch = result.match(/Blog=(\d+)\/(\d+)/);
    const faqMatch = result.match(/FAQ=(\d+)/);
    const googleMatch = result.match(/Google=(\d+)/);

    res.status(200).json({
      products: productsMatch ? parseInt(productsMatch[1]) : 0,
      blog_ok: blogMatch ? parseInt(blogMatch[1]) : 0,
      blog_fail: blogMatch ? parseInt(blogMatch[2]) - parseInt(blogMatch[1]) : 0,
      faq_seeded: faqMatch ? parseInt(faqMatch[1]) : 0,
      google: googleMatch ? parseInt(googleMatch[1]) : 0,
      raw: result.substring(result.length - 500),
    });
  } catch (e: any) {
    res.status(500).json({ error: e.message });
  }
}
