import { defineFunction } from '@aws-amplify/backend';

export const rcsDlr = defineFunction( {
    name: 'wecare-rcs-dlr',
    entry: './handler.py',
    runtime: 20, // Python 3.12
    timeoutSeconds: 15,
    memoryMB: 256,
    environment: {
        AWS_REGION: 'us-east-1',
        LOG_LEVEL: 'INFO',
        RCS_TABLE: 'stack-wecare-digital-RcsMessagesTable',
        CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    },
} );
