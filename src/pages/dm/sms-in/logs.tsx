/**
 * SMS-IN Logs Page
 * Uses AWS SMS API (Pinpoint/SNS) for message data - filters for inbound
 */
import { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';

interface PageProps { signOut?: () => void; user?: any; }
interface LogEntry { id: string; direction: string; contactId: string; contactName?: string; phone?: string; content: string; status: string; timestamp: string; }

const LOGS_PER_PAGE = 50;

export default function SmsInLogsPage({ signOut, user }: PageProps) {
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<'all' | 'inbound' | 'outbound'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [messagesData, contactsData] = await Promise.all([api.listSmsAwsMessages(), api.listContacts()]);
      const contactMap = new Map<string, api.Contact>();
      contactsData.forEach(c => contactMap.set(c.contactId, c));
      // Filter for inbound messages for SMS-IN page
      const inboundMessages = messagesData.filter(m => m.direction === 'INBOUND');
      setLogs(inboundMessages.map(m => ({
        id: m.messageId, direction: m.direction, contactId: m.contactId,
        contactName: contactMap.get(m.contactId)?.name, phone: m.phoneNumber || contactMap.get(m.contactId)?.phone,
        content: m.content || '', status: m.status || 'unknown', timestamp: m.timestamp ? new Date(m.timestamp * 1000).toISOString() : new Date().toISOString()
      })).sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()));
    } catch (err) { toast.error('Failed to load logs'); } finally { setLoading(false); }
  }, [toast]);

  useEffect(() => { loadData(); }, [loadData]);
  useEffect(() => { setPage(1); }, [filter, searchQuery]);

  const filteredLogs = logs.filter(log => {
    if (filter === 'inbound' && log.direction !== 'INBOUND') return false;
    if (filter === 'outbound' && log.direction !== 'OUTBOUND') return false;
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      return log.contactName?.toLowerCase().includes(q) || log.phone?.includes(q) || log.content.toLowerCase().includes(q);
    }
    return true;
  });

  const totalPages = Math.ceil(filteredLogs.length / LOGS_PER_PAGE);
  const paginatedLogs = filteredLogs.slice((page - 1) * LOGS_PER_PAGE, page * LOGS_PER_PAGE);

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="SMS-IN Logs | WECARE.DIGITAL" description="SMS-IN message logs" />
      <div className="inner-page logs-page">
        <div className="page-header"><h2>SMS-IN Logs</h2><Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} /></div>
        <div className="filters-row">
          <div className="filter-tabs">
            <button className={filter === 'all' ? 'active' : ''} onClick={() => setFilter('all')}>All ({logs.length})</button>
            <button className={filter === 'inbound' ? 'active' : ''} onClick={() => setFilter('inbound')}>Inbound ({logs.filter(l => l.direction === 'INBOUND').length})</button>
            <button className={filter === 'outbound' ? 'active' : ''} onClick={() => setFilter('outbound')}>Outbound ({logs.filter(l => l.direction === 'OUTBOUND').length})</button>
          </div>
          <input type="text" placeholder="Search logs..." value={searchQuery} onChange={e => setSearchQuery(e.target.value)} className="search-input" />
        </div>
        <div className="pagination-row"><Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} /></div>
        <div className="table-container">
          <table>
            <thead><tr><th>Time</th><th>Direction</th><th>Contact</th><th>Phone</th><th>Content</th><th>Status</th></tr></thead>
            <tbody>
              {paginatedLogs.map(log => (
                <tr key={log.id}>
                  <td>{new Date(log.timestamp).toLocaleString()}</td>
                  <td><span className={log.direction === 'INBOUND' ? 'badge-inbound' : 'badge-outbound'}>{log.direction === 'INBOUND' ? '↙ In' : '↗ Out'}</span></td>
                  <td>{log.contactName || '-'}</td>
                  <td>{log.phone || '-'}</td>
                  <td className="content-cell">{log.content.substring(0, 50)}{log.content.length > 50 ? '...' : ''}</td>
                  <td>{log.status}</td>
                </tr>
              ))}
              {paginatedLogs.length === 0 && <tr><td colSpan={6} className="empty-state">{loading ? 'Loading...' : 'No logs found'}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <style jsx>{`
        .logs-page { padding: 20px; background: #f0fdf4; min-height: calc(100vh - 60px); }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .page-header h2 { margin: 0; color: #065f46; }
        .filters-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 16px; }
        .filter-tabs { display: flex; gap: 8px; }
        .filter-tabs button { padding: 8px 16px; border: 1px solid #a7f3d0; background: #fff; border-radius: 8px; cursor: pointer; font-size: 13px; color: #047857; transition: all 0.15s; }
        .filter-tabs button:hover { background: #ecfdf5; }
        .filter-tabs button.active { background: #10b981; color: #fff; border-color: #10b981; }
        .search-input { padding: 8px 12px; border: 1px solid #a7f3d0; border-radius: 8px; width: 250px; background: #fff; }
        .search-input:focus { outline: none; border-color: #10b981; box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2); }
        .pagination-row { margin-bottom: 16px; }
        .table-container { overflow-x: auto; background: #fff; border-radius: 12px; border: 1px solid #d1fae5; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ecfdf5; font-size: 13px; }
        th { background: #ecfdf5; font-weight: 500; color: #065f46; }
        .badge-inbound { background: #10b981; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .badge-outbound { background: #059669; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .content-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #374151; }
        .empty-state { text-align: center; color: #047857; padding: 40px; }
        tr:hover { background: #f0fdf4; }
      `}</style>
    </Layout>
  );
}
