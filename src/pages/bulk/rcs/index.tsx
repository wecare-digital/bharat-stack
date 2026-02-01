/**
 * Bulk RCS - Rich Communication Services campaigns
 */

import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

export default function BulkRcs({ signOut, user }: PageProps) {
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
      docsLabel="IN RCS API Docs"
      user={user}
      signOut={signOut}
    />
  );
}
