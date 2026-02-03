/**
 * Invoice Create Page - Coming Soon
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const InvoiceCreatePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Create Invoice"
      subtitle="Create professional invoices with payment links"
      icon="create"
      backLink="/invoice"
      backLabel="← Invoices"
      features={[
        'Invoice Templates',
        'PDF Export',
        'Payment Links',
        'Tax Calculation',
        'Recurring Invoices',
        'Payment Reminders',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default InvoiceCreatePage;
