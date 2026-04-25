/**
 * API Route: /api/seo-tools/seo-logs
 * Returns audit history and AI logs.
 *
 * GET ?type=audits  → all audit records
 * GET ?type=logs    → all AI request/response logs
 * GET ?type=settings → automation settings
 */
import type { NextApiRequest, NextApiResponse } from 'next';
import { listAudits, listLogs, getSettings, updateSettings } from '../../../lib/seo-db';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const { type } = req.query;

  if (req.method === 'GET') {
    if (type === 'logs') return res.json({ ok: true, logs: listLogs() });
    if (type === 'settings') return res.json({ ok: true, settings: getSettings() });
    // Default: audits
    return res.json({ ok: true, audits: listAudits() });
  }

  if (req.method === 'POST' && type === 'settings') {
    const updated = updateSettings(req.body);
    return res.json({ ok: true, settings: updated });
  }

  res.status(405).json({ error: 'Method not allowed' });
}
