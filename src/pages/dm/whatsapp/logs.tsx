/**
 * WhatsApp Logs Page
 */
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';
import { useToastContext } from '../../../contexts/ToastContext';
import * as api from '../../../api/client';
import Button from '../../../components/ui/Button';
import Pagination from '../../../components/ui/Pagination';
import { describeWaError } from '../../../lib/wa-errors';
import InfoTooltip from '../../../components/ui/InfoTooltip';

interface PageProps { signOut?: () => void; user?: any; embedded?: boolean; }
interface LogEntry { id: string; direction: string; contactId: string; contactName?: string; phone?: string; bsuid?: string; username?: string; content: string; status: string; timestamp: string; templateName?: string; messageType?: string; transcription?: string; detectedLanguage?: string; errorCode?: number; errorDetails?: string; }

const LOGS_PER_PAGE = 50;

const WhatsAppLogsPage: React.FC<PageProps> = ( { signOut, user, embedded = false } ) => {
  const [ loading, setLoading ] = useState( false );
  const [ logs, setLogs ] = useState<LogEntry[]>( [] );
  const [ contacts, setContacts ] = useState<Map<string, api.Contact>>( new Map() );
  const [ page, setPage ] = useState( 1 );
  const [ filter, setFilter ] = useState<'all' | 'inbound' | 'outbound'>( 'all' );
  const [ searchQuery, setSearchQuery ] = useState( '' );
  const toast = useToastContext();

  const loadData = useCallback( async () => {
    setLoading( true );
    try
    {
      const [ messagesData, contactsData ] = await Promise.all( [
        api.listMessages( undefined, 'WHATSAPP' ),
        api.listContacts()
      ] );
      const contactMap = new Map<string, api.Contact>();
      contactsData.forEach( c => contactMap.set( c.contactId, c ) );
      setContacts( contactMap );
      setLogs( messagesData.map( m => ( {
        id: m.messageId,
        direction: m.direction,
        contactId: m.contactId,
        contactName: contactMap.get( m.contactId )?.name,
        phone: contactMap.get( m.contactId )?.phone,
        bsuid: contactMap.get( m.contactId )?.bsuid,
        username: contactMap.get( m.contactId )?.username,
        content: m.content || '',
        status: m.status || 'unknown',
        timestamp: m.timestamp,
        templateName: ( m as any ).templateName,
        messageType: m.messageType,
        transcription: m.transcription,
        detectedLanguage: m.detectedLanguage,
        errorCode: m.errorCode,
        errorDetails: m.errorDetails,
      } ) ).sort( ( a, b ) => new Date( b.timestamp ).getTime() - new Date( a.timestamp ).getTime() ) );
    } catch ( err ) { toast.error( 'Failed to load logs' ); } finally { setLoading( false ); }
  }, [ toast ] );

  useEffect( () => { loadData(); }, [ loadData ] );
  useEffect( () => { setPage( 1 ); }, [ filter, searchQuery ] );


  const filteredLogs = logs.filter( log => {
    if ( filter === 'inbound' && log.direction !== 'INBOUND' ) return false;
    if ( filter === 'outbound' && log.direction !== 'OUTBOUND' ) return false;
    if ( searchQuery )
    {
      const q = searchQuery.toLowerCase();
      return log.contactName?.toLowerCase().includes( q ) || log.phone?.includes( q ) || log.content.toLowerCase().includes( q ) || log.bsuid?.includes( q ) || log.username?.toLowerCase().includes( q );
    }
    return true;
  } );

  const totalPages = Math.ceil( filteredLogs.length / LOGS_PER_PAGE );
  const paginatedLogs = filteredLogs.slice( ( page - 1 ) * LOGS_PER_PAGE, page * LOGS_PER_PAGE );

  const getStatusColor = ( status: string ) => {
    switch ( status.toLowerCase() )
    {
      case 'read': return 'status-read';
      case 'delivered': return 'status-delivered';
      case 'sent': return 'status-sent';
      case 'failed': case 'undelivered': return 'status-failed';
      default: return 'status-queued';
    }
  };

  // ── Delivery report: counts, rates, failure breakdown, deleted-by-user ──
  const stats = useMemo( () => {
    const lc = ( s?: string ) => ( s || '' ).toLowerCase();
    const out = logs.filter( l => l.direction === 'OUTBOUND' );
    const inb = logs.filter( l => l.direction === 'INBOUND' );
    const cnt = ( arr: LogEntry[], s: string ) => arr.filter( l => lc( l.status ) === s ).length;
    const failedRows = out.filter( l => [ 'failed', 'undelivered' ].includes( lc( l.status ) ) );
    // A message a user deletes for everyone arrives as a `revoke` webhook.
    const deletedByUser = inb.filter( l => l.messageType === 'revoke' || /deleted by sender/i.test( l.content ) ).length;
    const sent = cnt( out, 'sent' );
    const delivered = cnt( out, 'delivered' );
    const read = cnt( out, 'read' );
    const failed = failedRows.length;
    const reachable = Math.max( 0, out.length - failed );
    const reasons: Record<string, number> = {};
    failedRows.forEach( l => {
      const info = describeWaError( l.errorCode, l.errorDetails );
      const key = l.errorCode ? `${l.errorCode} · ${info?.title || 'Error'}` : ( info?.title || 'Unknown reason' );
      reasons[ key ] = ( reasons[ key ] || 0 ) + 1;
    } );
    const topReasons = Object.entries( reasons ).sort( ( a, b ) => b[ 1 ] - a[ 1 ] ).slice( 0, 6 );
    return {
      outTotal: out.length, inTotal: inb.length,
      sent, delivered, read, failed, deletedByUser, reachable,
      readRate: reachable ? Math.round( ( read / reachable ) * 100 ) : 0,
      deliveredRate: reachable ? Math.round( ( ( delivered + read ) / reachable ) * 100 ) : 0,
      failRate: out.length ? Math.round( ( failed / out.length ) * 100 ) : 0,
      topReasons,
    };
  }, [ logs ] );

  const downloadLogsCsv = () => {
    const esc = ( v: any ) => { const s = String( v ?? '' ); return /[",\n]/.test( s ) ? `"${s.replace( /"/g, '""' )}"` : s; };
    const rows: string[][] = [ [ 'time', 'direction', 'contact', 'phone', 'type', 'template', 'status', 'errorCode', 'reason', 'content' ] ];
    filteredLogs.forEach( l => {
      const info = [ 'failed', 'undelivered' ].includes( ( l.status || '' ).toLowerCase() ) ? describeWaError( l.errorCode, l.errorDetails ) : null;
      rows.push( [
        new Date( l.timestamp ).toISOString(), l.direction, l.contactName || l.username || '', l.phone || l.bsuid || '',
        l.messageType || 'text', l.templateName || '', l.status, l.errorCode ? String( l.errorCode ) : '',
        info ? info.reason : '', l.content,
      ] );
    } );
    const csv = '\uFEFF' + rows.map( r => r.map( esc ).join( ',' ) ).join( '\r\n' );
    const url = URL.createObjectURL( new Blob( [ csv ], { type: 'text/csv;charset=utf-8;' } ) );
    const a = document.createElement( 'a' ); a.href = url; a.download = `whatsapp-logs-${Date.now()}.csv`; a.click();
    URL.revokeObjectURL( url );
  };

  const content = (
    <>
      <div className="inner-page logs-page">
        <div className="page-header">
          <h2>WhatsApp Logs</h2>
          <div style={ { display: 'flex', gap: 8 } }>
            <Button variant="secondary" onClick={ downloadLogsCsv } disabled={ loading || filteredLogs.length === 0 }>⬇ Export CSV</Button>
            <Button variant="secondary" icon="refresh" onClick={ loadData } disabled={ loading } loading={ loading }>Refresh</Button>
          </div>
        </div>
        {/* ── Delivery report ── */ }
        <div className="report-grid">
          <div className="report-card"><div className="rc-val">{ stats.outTotal }</div><div className="rc-label">Outbound</div></div>
          <div className="report-card"><div className="rc-val st-delivered">{ stats.delivered + stats.read }</div><div className="rc-label">Delivered <span className="rc-sub">{ stats.deliveredRate }%</span></div></div>
          <div className="report-card"><div className="rc-val st-read">{ stats.read }</div><div className="rc-label">Read <span className="rc-sub">{ stats.readRate }%</span></div></div>
          <div className="report-card"><div className="rc-val st-failed">{ stats.failed }</div><div className="rc-label">Failed <span className="rc-sub">{ stats.failRate }%</span></div></div>
          <div className="report-card"><div className="rc-val">{ stats.inTotal }</div><div className="rc-label">Inbound</div></div>
          <div className="report-card"><div className="rc-val">{ stats.deletedByUser }</div><div className="rc-label">Deleted by user</div></div>
        </div>
        { stats.topReasons.length > 0 && (
          <div className="reasons-card">
            <div className="reasons-title">Top failure reasons</div>
            <div className="reasons-list">
              { stats.topReasons.map( ( [ key, n ] ) => (
                <span key={ key } className="reason-chip" title={ key }>{ key } <strong>{ n }</strong></span>
              ) ) }
            </div>
          </div>
        ) }
        <div className="filters-row">
          <div className="filter-tabs">
            <button className={ filter === 'all' ? 'active' : '' } onClick={ () => setFilter( 'all' ) }>All ({ logs.length })</button>
            <button className={ filter === 'inbound' ? 'active' : '' } onClick={ () => setFilter( 'inbound' ) }>Inbound ({ logs.filter( l => l.direction === 'INBOUND' ).length })</button>
            <button className={ filter === 'outbound' ? 'active' : '' } onClick={ () => setFilter( 'outbound' ) }>Outbound ({ logs.filter( l => l.direction === 'OUTBOUND' ).length })</button>
          </div>
          <input type="text" placeholder="Search logs..." value={ searchQuery } onChange={ e => setSearchQuery( e.target.value ) } className="search-input" />
        </div>
        <div className="pagination-row"><Pagination currentPage={ page } totalPages={ totalPages } onPageChange={ setPage } /></div>
        <div className="table-container">
          <table>
            <thead><tr><th>Time</th><th>Direction</th><th>Contact</th><th>Phone</th><th>Type</th><th>Content</th><th>Template</th><th>Status</th></tr></thead>
            <tbody>
              { paginatedLogs.map( log => (
                <tr key={ log.id }>
                  <td>{ new Date( log.timestamp ).toLocaleString() }</td>
                  <td><span className={ log.direction === 'INBOUND' ? 'badge-inbound' : 'badge-outbound' }>{ log.direction === 'INBOUND' ? '↙ In' : '↗ Out' }</span></td>
                  <td>{ log.contactName || log.username ? `@${log.username}` : '-' }</td>
                  <td>{ log.phone || ( log.bsuid ? '🆔 ' + log.bsuid.slice( 0, 16 ) + '...' : '-' ) }</td>
                  <td>{ log.messageType === 'audio' ? '🎤' : log.messageType === 'image' ? '🖼️' : log.messageType === 'video' ? '🎬' : log.messageType === 'document' ? '📄' : '💬' }</td>
                  <td className="content-cell" title={ log.transcription || log.content }>{ log.messageType === 'audio' && log.transcription ? `📝 ${log.transcription.substring( 0, 40 )}${log.transcription.length > 40 ? '...' : ''}` : log.content.substring( 0, 50 ) }{ !log.transcription && log.content.length > 50 ? '...' : '' }</td>
                  <td>{ log.templateName || '-' }</td>
                  <td>
                    { ( [ 'failed', 'undelivered' ].includes( ( log.status || '' ).toLowerCase() ) ) ? (
                      ( () => {
                        let raw = '';
                        try { raw = log.errorDetails ? ( JSON.parse( log.errorDetails )?.message || '' ) : ''; } catch { raw = log.errorDetails || ''; }
                        const info = describeWaError( log.errorCode, raw );
                        const tipContent = info ? (
                          <>
                            <div style={ { fontWeight: 700, marginBottom: 4 } }>{ log.errorCode ? `${log.errorCode} · ` : '' }{ info.title }</div>
                            <div style={ { marginBottom: 6 } }>{ info.reason }</div>
                            <div style={ { color: '#4b5563' } }><strong>Fix:</strong> { info.action }</div>
                          </>
                        ) : 'Message failed.';
                        return (
                          <span className="status-pill status-failed">
                            { log.status }{ ' ' }
                            <InfoTooltip content={ tipContent } label="Why this message failed" />
                          </span>
                        );
                      } )()
                    ) : (
                      <span className={ `status-pill ${getStatusColor( log.status )}` }>{ log.status }</span>
                    ) }
                  </td>
                </tr>
              ) ) }
              { paginatedLogs.length === 0 && <tr><td colSpan={ 8 } className="empty-state">{ loading ? 'Loading...' : 'No logs found' }</td></tr> }
            </tbody>
          </table>
        </div>
      </div>
      <style jsx>{ `
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
        .report-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-bottom: 16px; }
        @media (max-width: 768px) { .report-grid { grid-template-columns: repeat(2, 1fr); } }
        .report-card { background: var(--bg-secondary, #f9fafb); border: 1.5px solid var(--border, #e5e7eb); border-radius: 12px; padding: 14px 16px; }
        .rc-val { font-size: 26px; font-weight: 700; color: var(--text, #111827); line-height: 1.1; }
        .rc-label { font-size: 12px; color: var(--text-muted, #6b7280); margin-top: 4px; font-weight: 600; }
        .rc-sub { font-weight: 700; color: var(--text-secondary, #4b5563); }
        .rc-val.st-delivered { color: var(--status-delivered, #14b8a6); }
        .rc-val.st-read { color: var(--status-read, #22c55e); }
        .rc-val.st-failed { color: var(--status-failed, #ef4444); }
        .reasons-card { background: #fff; border: 1.5px solid var(--border, #e5e7eb); border-radius: 12px; padding: 12px 16px; margin-bottom: 16px; }
        .reasons-title { font-size: 12px; font-weight: 700; color: var(--text-muted, #6b7280); text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 8px; }
        .reasons-list { display: flex; flex-wrap: wrap; gap: 8px; }
        .reason-chip { font-size: 12px; padding: 4px 10px; border-radius: 9999px; background: var(--status-failed-bg, #fef2f2); color: var(--status-failed-fg, #b91c1c); white-space: nowrap; }
        .text-success { color: #1a3a2a; }
        .text-error { color: #1a3a2a; }
        .empty-state { text-align: center; color: #6b7280; padding: 40px; }
      `}</style>
    </>
  );

  if ( embedded ) return content;

  return (
    <Layout user={ user } onSignOut={ signOut }>
      <SEO title="WhatsApp Logs" description="WhatsApp message logs" />
      { content }
    </Layout>
  );
};

export default WhatsAppLogsPage;