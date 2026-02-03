/**
 * RCS Logs Page
 * Rich Communication Services logs
 */

import React from 'react';
import Layout from '../../../components/Layout';
import SEO from '../../../components/SEO';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const RcsLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <Layout user={user} onSignOut={signOut}>
      <SEO title="RCS Logs | WECARE.DIGITAL" description="RCS message logs" />
      <div style={{ padding: '20px' }}>
        <h2 style={{ margin: '0 0 20px' }}>RCS - Logs</h2>
        
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: '12px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f9fafb' }}>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>To</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Message</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '12px 16px', textAlign: 'left', borderBottom: '1px solid #e5e7eb', fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase' }}>Date</th>
              </tr>
            </thead>
            <tbody>
              <tr><td colSpan={4} style={{ padding: '40px', textAlign: 'center', color: '#6b7280' }}>No RCS logs yet - Coming soon</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </Layout>
  );
};

export default RcsLogsPage;
