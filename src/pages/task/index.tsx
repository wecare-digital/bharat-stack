/**
 * Task Management - Coming Soon
 */

import React from 'react';
import ComingSoon from '../../components/ComingSoon';

interface PageProps {
  signOut?: () => void;
  user?: any;
}

const TaskPage: React.FC<PageProps> = ({ signOut, user }) => {
  return (
    <ComingSoon
      title="Task Management"
      subtitle="Organize and track your tasks efficiently"
      icon="checklist"
      features={[
        'Create and assign tasks',
        'Set priorities and deadlines',
        'Track progress and completion',
        'Team collaboration',
        'Task templates',
        'Automated reminders',
      ]}
      user={user}
      signOut={signOut}
    />
  );
};

export default TaskPage;
