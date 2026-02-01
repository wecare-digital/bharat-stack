/**
 * Invoice - Invoice Logs
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
      title="Invoice History"
      subtitle="View all generated invoices"
      icon="logs"
      backLink="/invoice"
      backLabel="← Invoice"
      features={[
        'Invoice History',
        'Payment Status',
        'Download PDFs',
        'Send Reminders',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default InvoiceLogsPage;
