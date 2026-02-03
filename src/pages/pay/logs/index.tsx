/**
 * Payment Logs Page - Coming Soon
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const PayLogsPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Payment Logs"
      subtitle="Track all payment transactions and refunds"
      icon="logs"
      backLink="/pay"
      backLabel="← Payments"
      features={[
        'Transaction History',
        'Refund Tracking',
        'Settlement Reports',
        'Revenue Analytics',
        'Export Data',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default PayLogsPage;
