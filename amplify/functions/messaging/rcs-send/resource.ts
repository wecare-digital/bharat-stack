import { defineFunction } from '@aws-amplify/backend';

export const rcsSend = defineFunction( {
    name: 'wecare-rcs-send',
    entry: './handler.py',
    runtime: 20, // Python 3.12
    timeoutSeconds: 30,
    memoryMB: 256,
    environment: {
        AWS_REGION: 'us-east-1',
        LOG_LEVEL: 'INFO',
        RCS_TABLE: 'stack-wecare-digital-RcsMessagesTable',
        CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
        RCS_SECRET_NAME: 'wecare/sinch/rcs',
        RCS_PROJECT_ID: 'c8114d03-eeb2-401d-a8f1-abb93594cb33',
        RCS_APP_ID: '01KQSB792X3R148D8ZGHQYW3SP',
    },
} );
