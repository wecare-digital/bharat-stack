/**
 * Link Create - Create Shareable Links
 */

import React from 'react';
import ComingSoon from '../../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const LinkCreatePage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Create Link"
      subtitle="Create shareable links for payments, forms, and more"
      icon="create"
      backLink="/link"
      backLabel="Link"
      features={[
        'Short URLs',
        'Payment Links',
        'Form Links',
        'QR Codes',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default LinkCreatePage;
