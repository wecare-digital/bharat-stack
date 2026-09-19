import { defineFunction } from '@aws-amplify/backend';

// SMS is sent exclusively through AWS End User Messaging (pinpoint-sms-voice-v2).
// Region selection, the India DLT entity/sender/template and E.164 normalisation
// all live in lambda_utils/comms, so this function needs no provider configuration
// of its own.
//
// Removed 2026-09-19, together with the prohibited senders in handler.py: the
// legacy AWS SMS application id, the superseded origination-number and sender-id
// pair, and six variables configuring a retired Indian operator's A2P API
// (host, username, password, customer id, entity id and header). The two
// regulatory values among them are now owned by lambda_utils/comms/dlt.py.
//
// Identifier names are deliberately not repeated here, so the provider-policy
// scan stays high-precision over runtime configuration.
// See docs/provider-retirement-inventory.md for the full removed surface.
export const outboundSms = defineFunction({
  name: 'wecare-outbound-sms',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    MESSAGES_TABLE: 'stack-wecare-digital-MessagesTable',
  },
});
