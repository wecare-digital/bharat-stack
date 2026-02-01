/**
 * Bulk RCS - Airtel IQ
 * Bulk RCS campaigns via Airtel IQ RCS API
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const BulkRcs: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Bulk RCS"
      subtitle="Rich Communication Services campaigns"
      icon="rcs"
      backLink="/bulk"
      backLabel="← Bulk"
      features={[
        'Rich Media Messages',
        'Carousels & Cards',
        'Quick Reply Buttons',
        'Read Receipts',
        'Campaign Analytics',
      ]}
      docsUrl="https://www.airtel.in/business/b2b/airtel-iq/api-docs/rcs/overview"
      docsLabel="Airtel IQ RCS API Docs"
      user={user}
      signOut={signOut}
    />
  );
};

export default BulkRcs;
