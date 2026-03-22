/**
 * Ad Attribution Dashboard
 * View Click-to-WhatsApp ad attribution stats and click history.
 * Fetches data from the ad-attribution Lambda handler.
 */
import React, { useState, useEffect, useCallback } from 'react';
import * as api from '../api/client';

interface AdAttributionDashboardProps {
  onClose?: () => void;
}

interface AdClick {
  id: string;
  phone: string;
  contactId: string;
  sourceType: string;
  sourceId: string;
  sourceUrl: string;
  headline: string;
  body: string;
  createdAt: number;
}

interface AdStats {
  totalClicks: number;
  uniqueContacts: number;
  bySource: Record<string, number>;
  last7Days: number;
  last30Days: number;
}

const AdAttributionDashboard: React.FC<AdAttributionDashboardProps> = ({ onClose }) => {
  const [clicks, setClicks] = useState<AdClick[]>([]);
  const [stats, setStats] = useState<AdStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<'stats' | 'clicks'>('stats');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, clicksRes] = await Promise.all([
        api.getAdAttributionStats(),
        api.getAdAttributionClicks({ limit: 50 }),
      ]);
      setStats(statsRes?.stats || null);
      setClicks(clicksRes?.attributions || []);
    } catch {
      // Silently handle — dashboard is informational
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const formatDate = (ts: number) => new Date(ts * 1000).toLocaleDateString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });

  return (
    <div className="p-4 border rounded-lg bg-white shadow-sm">
      <div className="flex justify-between items-center mb-3">
        <h3 className="font-medium text-sm">Ad Attribution</h3>
        {onClose && (
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg" aria-label="Close">&times;</button>
        )}
      </div>
      <div className="flex gap-2 mb-3">
        <button onClick={() => setTab('stats')}
          className={`px-3 py-1 text-xs rounded ${tab === 'stats' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}>
          Stats
        </button>
        <button onClick={() => setTab('clicks')}
          className={`px-3 py-1 text-xs rounded ${tab === 'clicks' ? 'bg-blue-600 text-white' : 'bg-gray-100'}`}>
          Click History
        </button>
      </div>
      {loading && <p className="text-sm text-gray-500">Loading...</p>}
      {!loading && tab === 'stats' && stats && (
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="border rounded p-3 text-center">
            <p className="text-2xl font-bold text-blue-600">{stats.totalClicks}</p>
            <p className="text-xs text-gray-500">Total Clicks</p>
          </div>
          <div className="border rounded p-3 text-center">
            <p className="text-2xl font-bold text-green-600">{stats.uniqueContacts}</p>
            <p className="text-xs text-gray-500">Unique Contacts</p>
          </div>
          <div className="border rounded p-3 text-center">
            <p className="text-2xl font-bold">{stats.last7Days}</p>
            <p className="text-xs text-gray-500">Last 7 Days</p>
          </div>
          <div className="border rounded p-3 text-center">
            <p className="text-2xl font-bold">{stats.last30Days}</p>
            <p className="text-xs text-gray-500">Last 30 Days</p>
          </div>
          {stats.bySource && Object.keys(stats.bySource).length > 0 && (
            <div className="col-span-2 border rounded p-3">
              <p className="text-xs text-gray-500 mb-1">By Source</p>
              {Object.entries(stats.bySource).map(([src, count]) => (
                <div key={src} className="flex justify-between text-xs py-0.5">
                  <span>{src}</span><span className="font-medium">{count}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
      {!loading && tab === 'clicks' && (
        <div className="max-h-80 overflow-y-auto">
          {clicks.length === 0 && <p className="text-sm text-gray-500">No ad clicks recorded yet.</p>}
          {clicks.map(click => (
            <div key={click.id} className="border-b py-2 text-xs">
              <div className="flex justify-between">
                <span className="font-medium">{click.sourceType || 'unknown'}</span>
                <span className="text-gray-400">{formatDate(click.createdAt)}</span>
              </div>
              {click.headline && <p className="text-gray-600">{click.headline}</p>}
              <p className="text-gray-400 truncate">{click.sourceUrl}</p>
            </div>
          ))}
        </div>
      )}
      <button onClick={fetchData} className="mt-2 text-xs text-blue-600 hover:underline">🔄 Refresh</button>
    </div>
  );
};

export default AdAttributionDashboard;
