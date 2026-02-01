/**
 * Invoice - Create New Invoice
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
      subtitle="Generate professional invoices"
      icon="create"
      backLink="/invoice"
      backLabel="← Invoice"
      features={[
        'Invoice Templates',
        'Line Items',
        'Tax Calculations',
        'PDF Export',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default InvoiceCreatePage;
