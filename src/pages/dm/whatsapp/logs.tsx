/**
 * WhatsApp Logs Page
 */
import React, { useState, useEffect, useCallback } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }
interface LogEntry { id: string; direction: string; contactId: string; contactName?: string; phone?: string; content: string; status: string; timestamp: string; templateName?: string; }

const LOGS_PER_PAGE = 50;

const WhatsAppLogsPage: React.FC<PageProps> = ({ signOut, user, embedded = false }) => {
  const [loading, setLoading] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [contacts, setContacts] = useState<Map<string, api.Contact>>(new Map());
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState<'all' | 'inbound' | 'outbound'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const toast = useToastContext();

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [messagesData, contactsData] = await Promise.all([
        api.listMessages(undefined, 'WHATSAPP'),
        api.listContacts()
      ]);
      const contactMap = new Map<string, api.Contact>();
      contactsData.forEach(c => contactMap.set(c.contactId, c));
      setContacts(contactMap);
      setLogs(messagesData.map(m => ({
        id: m.messageId,
        direction: m.direction,
        contactId: m.contactId,
        contactName: contactMap.get(m.contactId)?.name,
        phone: contactMap.get(m.contactId)?.phone,
        content: m.content || '',
        status: m.status || 'unknown',
        timestamp: m.timestamp,
        templateName: (m as any).templateName
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

  const getStatusColor = (status: string) => {
    switch (status.toLowerCase()) {
      case 'delivered': case 'read': case 'sent': return 'text-success';
      case 'failed': case 'undelivered': return 'text-error';
      default: return '';
    }
  };

  const content = (
    <>
      <div className="inner-page logs-page">
        <div className="page-header">
          <h2>WhatsApp Logs</h2>
          <Button variant="secondary" icon="refresh" iconOnly ariaLabel="Refresh" onClick={loadData} disabled={loading} loading={loading} />
        </div>
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
            <thead><tr><th>Time</th><th>Direction</th><th>Contact</th><th>Phone</th><th>Content</th><th>Template</th><th>Status</th></tr></thead>
            <tbody>
              {paginatedLogs.map(log => (
                <tr key={log.id}>
                  <td>{new Date(log.timestamp).toLocaleString()}</td>
                  <td><span className={log.direction === 'INBOUND' ? 'badge-inbound' : 'badge-outbound'}>{log.direction === 'INBOUND' ? '↙ In' : '↗ Out'}</span></td>
                  <td>{log.contactName || '-'}</td>
                  <td>{log.phone || '-'}</td>
                  <td className="content-cell">{log.content.substring(0, 50)}{log.content.length > 50 ? '...' : ''}</td>
                  <td>{log.templateName || '-'}</td>
                  <td className={getStatusColor(log.status)}>{log.status}</td>
                </tr>
              ))}
              {paginatedLogs.length === 0 && <tr><td colSpan={7} className="empty-state">{loading ? 'Loading...' : 'No logs found'}</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
      <style jsx>{`
        .logs-page { padding: 20px; }
        .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .page-header h2 { margin: 0; }
        .filters-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; gap: 16px; }
        .filter-tabs { display: flex; gap: 8px; }
        .filter-tabs button { padding: 8px 16px; border: 1px solid #e5e5e5; background: #fff; border-radius: 8px; cursor: pointer; font-size: 13px; }
        .filter-tabs button.active { background: #000; color: #fff; border-color: #000; }
        .search-input { padding: 8px 12px; border: 1px solid #e5e5e5; border-radius: 8px; width: 250px; }
        .pagination-row { margin-bottom: 16px; }
        .table-container { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #e5e5e5; font-size: 13px; }
        th { background: #f9f9f9; font-weight: 500; }
        .badge-inbound { background: #000; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .badge-outbound { background: #6b7280; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; }
        .content-cell { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .text-success { color: #059669; }
        .text-error { color: #dc2626; }
        .empty-state { text-align: center; color: #6b7280; padding: 40px; }
      `}</style>
    </>
  );

  if (embedded) return content;

  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="WhatsApp Logs | WECARE.DIGITAL" description="WhatsApp message logs" />
      {content}
    </Layout>
  );
};

export default WhatsAppLogsPage;