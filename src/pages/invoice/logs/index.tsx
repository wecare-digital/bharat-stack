/**
 * Invoice Logs Page - Coming Soon
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const InvoiceLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Invoice Logs"
      subtitle="Track invoice status and payment history"
      icon="logs"
      backLink="/invoice"
      backLabel="← Invoices"
      features={[
        'Payment Status',
        'Due Date Tracking',
        'Overdue Alerts',
        'Revenue Reports',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default InvoiceLogsPage;
