/**
 * RCS DM - Rich Communication Services
 */

import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

export default function RcsDM({ signOut, user }: PageProps) {
  return (
    <ComingSoon
      title="RCS"
      subtitle="Rich Communication Services"
      icon="rcs"
      backLink="/dm"
      backLabel="← Messages"
      features={[
        'Rich Media Messages',
        'Carousels & Cards',
        'Quick Reply Buttons',
        'Suggested Actions',
        'Branded Messaging',
        'Read Receipts',
        'Typing Indicators',
      ]}
      docsUrl="https://www.airtel.in/business/b2b/airtel-iq/api-docs/rcs/overview"
      docsLabel="IN RCS API Docs"
      user={user}
      signOut={signOut}
    />
  );
}
