/**
 * External AI Configuration Page (WhatsApp Auto-Reply)
 * 
 * REMOVED — WhatsApp AI auto-reply has been permanently disabled.
 * This page now shows a notice that the feature is removed.
 */

import Layout from '../../../components/Layout';
import PageHeader from '../../../components/PageHeader';

interface PageProps {
  signOut?: () => void;
  user?: any;
  embedded?: boolean;
}

export default function AIConfigPage ( { signOut, user, embedded = false }: PageProps ) {
  return (
    <Layout>
      <PageHeader
        title="WhatsApp AI Auto-Reply"
        subtitle="This feature has been permanently removed"
        icon="ai"
      />
      <div style={ { padding: '2rem', textAlign: 'center' } }>
        <div style={ {
          background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: 8,
          padding: '2rem', maxWidth: 600, margin: '2rem auto'
        } }>
          <h3 style={ { color: '#92400e', margin: '0 0 1rem' } }>⚠️ Feature Removed</h3>
          <p style={ { color: '#78350f' } }>
            WhatsApp AI auto-reply has been permanently disabled.
            Messages are handled by keyword triggers and manual responses only.
          </p>
          <p style={ { color: '#78350f', marginTop: '1rem', fontSize: '0.9rem' } }>
            The internal FloatingAgent (admin AI assistant) is still available in the dashboard.
          </p>
        </div>
      </div>
    </Layout>
  );
}
