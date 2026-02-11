# Requirements Document

## Introduction

This document specifies the requirements for a production-ready reference implementation that integrates WhatsApp messaging exclusively through AWS End User Messaging (EUM) Social. The system provides inbound message processing (SNS-triggered), outbound message sending (HTTP-triggered), media handling, template management, contact management, idempotent event processing, and operational tooling. All provisioning uses AWS CLI + SDK only (NO SAM, NO CloudFormation, NO CDK). The implementation language is Python + boto3. No direct Meta Graph API calls are permitted — all WhatsApp operations flow through the AWS EUM Social service.

## Glossary

- **EUM_Social_Service**: The AWS End User Messaging Social service that abstracts Meta's WhatsApp Cloud API, exposing 21 API operations via the `socialmessaging` boto3 client
- **Inbound_Handler**: The Lambda function triggered by SNS that processes incoming WhatsApp events (messages, statuses, template updates, quality updates, account updates)
- **Outbound_Sender**: The Lambda function triggered by HTTP (API Gateway) that sends WhatsApp messages via `SendWhatsAppMessage`
- **SNS_Event_Envelope**: The JSON wrapper that AWS EUM Social places around Meta webhook payloads, containing `context`, `whatsAppWebhookEntry`, `aws_account_id`, `message_timestamp`, and `messageId`
- **Meta_Webhook_Payload**: The standard Meta webhook JSON inside `whatsAppWebhookEntry`, containing `entry[].changes[].value.messages[]`, `entry[].changes[].value.statuses[]`, and field-level events
- **Normalized_Event**: The internal canonical representation of a WhatsApp event after parsing the SNS envelope and Meta webhook payload
- **WABA**: WhatsApp Business Account, identified by an AWS-assigned ID (e.g., `waba-xxx`) and a Meta-assigned numeric ID
- **Origination_Phone_Number_ID**: The AWS EUM Social phone number identifier (format: `phone-number-id-xxx`) used in all API calls
- **Customer_Service_Window**: The 24-hour period after a user's last inbound message during which free-form (non-template) messages can be sent
- **Idempotency_Table**: A DynamoDB table with TTL that stores processed event IDs to prevent duplicate processing
- **DLQ**: Dead Letter Queue (SQS) that captures failed processing attempts for later replay
- **Provisioning_Script**: A Bash or PowerShell script that uses AWS CLI commands to create and configure AWS resources
- **Replay_Tool**: A local CLI utility that reads SNS event fixtures and invokes the Inbound_Handler locally for testing
- **E164_Validator**: A utility that validates and normalizes phone numbers to E.164 international format
- **Social_Client_Wrapper**: A shared Python module that wraps the `socialmessaging` boto3 client with retry logic, exponential backoff, and error classification
- **Coverage_Gap_Matrix**: A mapping table that documents which Meta WhatsApp capabilities are available, partially available, or unavailable through AWS EUM Social

## Requirements

### Requirement 1: Inbound Event Processing

**User Story:** As a system operator, I want the Inbound_Handler to receive and process all WhatsApp events delivered via SNS, so that inbound messages, delivery statuses, and system events are captured reliably.

#### Acceptance Criteria

1. WHEN the SNS_Event_Envelope is received, THE Inbound_Handler SHALL extract the `whatsAppWebhookEntry` field and parse it as JSON to obtain the Meta_Webhook_Payload
2. WHEN the Meta_Webhook_Payload contains `entry[].changes[].value.messages[]`, THE Inbound_Handler SHALL iterate each message and create a Normalized_Event with fields: `event_id`, `message_type`, `sender_phone`, `sender_name`, `receiving_phone`, `content`, `media_id`, `timestamp`, `raw_payload`
3. WHEN the Meta_Webhook_Payload contains `entry[].changes[].value.statuses[]`, THE Inbound_Handler SHALL update the corresponding message record with the new status (`sent`, `delivered`, `read`, `failed`) and the status timestamp
4. WHEN the Meta_Webhook_Payload contains a `message_template_status_update` field event, THE Inbound_Handler SHALL persist the template status change (APPROVED, REJECTED, PAUSED) with the template name and reason
5. WHEN the Meta_Webhook_Payload contains a `phone_number_quality_update` field event, THE Inbound_Handler SHALL persist the quality rating change (GREEN, YELLOW, RED) with the phone number identifier
6. WHEN the Meta_Webhook_Payload contains an `account_update` field event, THE Inbound_Handler SHALL persist the account change (messaging limit updates, restrictions) with the WABA identifier
7. THE Inbound_Handler SHALL support all 18 inbound message types: `text`, `image`, `video`, `audio`, `document`, `sticker`, `location`, `contacts`, `reaction`, `interactive` (button_reply, list_reply, nfm_reply), `button`, `order`, `system`, `unsupported`, `request_welcome`, `ephemeral`
8. WHEN a message of type `image`, `video`, `audio`, `document`, or `sticker` is received, THE Inbound_Handler SHALL call `GetWhatsAppMessageMedia` to download the media to S3 and store the S3 key, MIME type, and file size in the media record
9. IF the `whatsAppWebhookEntry` field is missing or contains invalid JSON, THEN THE Inbound_Handler SHALL log the error with the full SNS record and send the record to the DLQ
10. WHEN the SNS_Event_Envelope contains `context.MetaWabaIds` and `context.MetaPhoneNumberIds`, THE Inbound_Handler SHALL include these identifiers in the Normalized_Event for multi-WABA routing

### Requirement 2: Outbound Message Sending

**User Story:** As an application developer, I want the Outbound_Sender to send all WhatsApp message types through AWS EUM Social, so that the system can communicate with WhatsApp users without calling Meta's Graph API directly.

#### Acceptance Criteria

1. WHEN a text message request is received with a valid `recipient_phone` and `content` (1–4096 characters), THE Outbound_Sender SHALL call `SendWhatsAppMessage` with the base64-encoded WhatsApp message payload and return the `messageId`
2. WHEN a media message request is received with a `source_s3_key` or base64-encoded file, THE Outbound_Sender SHALL first call `PostWhatsAppMessageMedia` to upload the media, then call `SendWhatsAppMessage` with the resulting `mediaId` in the message payload
3. WHEN a template message request is received with `template_name`, `language_code`, and optional `parameters[]`, THE Outbound_Sender SHALL construct the template payload and call `SendWhatsAppMessage`
4. WHEN an interactive message request is received with `interactive_type` (one of: `list`, `button`, `cta_url`, `location_request`, `flow`), THE Outbound_Sender SHALL construct the interactive payload respecting WhatsApp limits (max 3 reply buttons, max 10 list sections, max 10 rows per section) and call `SendWhatsAppMessage`
5. WHEN a reaction request is received with `message_id` and `emoji`, THE Outbound_Sender SHALL construct the reaction payload and call `SendWhatsAppMessage`
6. WHEN a read receipt request is received with `message_id`, THE Outbound_Sender SHALL construct the status-read payload and call `SendWhatsAppMessage`
7. THE Outbound_Sender SHALL validate that the `recipient_phone` conforms to E.164 format before sending
8. THE Outbound_Sender SHALL persist every sent message (except reactions and read receipts) to the MessagesTable with fields: `message_id`, `recipient_phone`, `content`, `message_type`, `status`, `whatsapp_message_id`, `phone_number_id`, `timestamp`
9. IF `SendWhatsAppMessage` returns a `ThrottledRequestException`, THEN THE Outbound_Sender SHALL return HTTP 429 with a `Retry-After` header
10. IF `SendWhatsAppMessage` returns any other error, THEN THE Outbound_Sender SHALL persist the message with `status=failed`, log the error code and message, and return the error to the caller

### Requirement 3: Idempotent Event Processing

**User Story:** As a system operator, I want duplicate SNS events to be detected and skipped, so that messages are not processed or stored more than once.

#### Acceptance Criteria

1. WHEN the Inbound_Handler receives an event, THE Inbound_Handler SHALL compute a deduplication key from the `whatsappMessageId` (for messages) or a composite of `messageId + status` (for statuses)
2. WHEN the deduplication key already exists in the Idempotency_Table, THE Inbound_Handler SHALL skip processing and return success
3. WHEN the deduplication key does not exist, THE Inbound_Handler SHALL write the key to the Idempotency_Table with a TTL of 48 hours before processing the event
4. THE Idempotency_Table SHALL use a TTL attribute to automatically expire entries after 48 hours

### Requirement 4: Contact Management

**User Story:** As a system operator, I want contacts to be automatically created or updated when inbound messages arrive, so that the system maintains an up-to-date contact directory.

#### Acceptance Criteria

1. WHEN an inbound message is received from a phone number not in the ContactsTable, THE Inbound_Handler SHALL create a new contact record with `phone` (E.164), `name` (from the WhatsApp profile), `opt_in_whatsapp=true`, `created_at`, and `last_inbound_at`
2. WHEN an inbound message is received from a phone number already in the ContactsTable, THE Inbound_Handler SHALL update the `last_inbound_at` timestamp and the `name` field if the WhatsApp profile name has changed
3. THE ContactsTable SHALL have a GSI on the `phone` attribute to enable efficient lookup by phone number without table scans

### Requirement 5: DynamoDB Data Model

**User Story:** As a system architect, I want well-defined DynamoDB table schemas with appropriate keys and indexes, so that all data access patterns are efficient and consistent.

#### Acceptance Criteria

1. THE MessagesTable SHALL use `message_id` (UUID) as the partition key and store fields: `message_type`, `direction` (inbound/outbound), `sender_phone`, `recipient_phone`, `content`, `media_id`, `s3_key`, `status`, `whatsapp_message_id`, `phone_number_id`, `waba_id`, `timestamp`, `expires_at` (TTL)
2. THE MessagesTable SHALL have a GSI on `whatsapp_message_id` to enable efficient status update lookups
3. THE ConversationsTable SHALL use `conversation_id` (composite of sorted phone numbers) as the partition key and store fields: `contact_phone`, `business_phone`, `last_message_at`, `last_inbound_at`, `window_expires_at`, `status` (active/expired)
4. THE ContactsTable SHALL use `contact_id` (UUID) as the partition key and store fields: `phone`, `name`, `opt_in_whatsapp`, `last_inbound_at`, `created_at`, `updated_at`
5. THE IdempotencyTable SHALL use `dedup_key` (string) as the partition key and store fields: `processed_at`, `expires_at` (TTL)
6. THE TemplatesTable SHALL use `template_id` (composite of WABA ID + template name) as the partition key and store fields: `meta_template_id`, `category`, `language`, `status`, `quality_score`, `last_synced_at`
7. WHEN a message record has a TTL `expires_at` value, THE DynamoDB service SHALL automatically delete the record after the TTL expires

### Requirement 6: Media Handling

**User Story:** As a system operator, I want media files to be uploaded and downloaded through AWS EUM Social's S3-based media operations, so that media is stored durably and served efficiently.

#### Acceptance Criteria

1. WHEN downloading inbound media, THE Inbound_Handler SHALL call `GetWhatsAppMessageMedia` with `destinationS3File` specifying the S3 bucket and a key following the pattern `{media_prefix}/{date}/{media_id}.{extension}`
2. WHEN uploading outbound media, THE Outbound_Sender SHALL call `PostWhatsAppMessageMedia` with `sourceS3File` specifying the S3 bucket and key where the file was staged
3. THE Media handling code SHALL validate file sizes against WhatsApp limits: images ≤ 5MB, video ≤ 16MB, audio ≤ 16MB, documents ≤ 100MB, static stickers ≤ 100KB, animated stickers ≤ 500KB
4. WHEN `GetWhatsAppMessageMedia` is called with `metadataOnly=true`, THE response SHALL return only `fileSize` and `mimeType` without downloading the file
5. IF a media download or upload fails, THEN THE handler SHALL log the error and continue processing the message without the media attachment

### Requirement 7: SNS Event Destination Setup

**User Story:** As a system operator, I want the SNS topic correctly configured as the WABA event destination, so that all WhatsApp events are reliably delivered to the Inbound_Handler.

#### Acceptance Criteria

1. THE SNS topic policy SHALL grant `sns:Publish` permission to the `social-messaging.amazonaws.com` service principal
2. WHEN configuring the event destination, THE Provisioning_Script SHALL call `PutWhatsAppBusinessAccountEventDestinations` with the SNS topic ARN and the IAM role ARN that grants EUM Social permission to publish
3. THE SNS topic SHALL have a subscription to the Inbound_Handler Lambda function with a DLQ configured for failed deliveries
4. THE IAM role for the event destination SHALL have a trust policy allowing `social-messaging.amazonaws.com` to assume it, and a permission policy allowing `sns:Publish` on the specific topic ARN

### Requirement 8: Provisioning Scripts

**User Story:** As a DevOps engineer, I want CLI-based provisioning scripts that create all AWS resources without SAM or CloudFormation, so that the infrastructure can be set up reproducibly using AWS CLI commands.

#### Acceptance Criteria

1. THE Provisioning_Script suite SHALL create all DynamoDB tables (MessagesTable, ConversationsTable, ContactsTable, IdempotencyTable, TemplatesTable) with PAY_PER_REQUEST billing and specified GSIs
2. THE Provisioning_Script suite SHALL create Lambda functions from zip-based deployment packages with the correct IAM role, runtime (Python 3.12), handler (`handler.handler`), timeout, and memory settings
3. THE Provisioning_Script suite SHALL create the SNS topic, set the topic policy, and create the Lambda subscription with DLQ redrive
4. THE Provisioning_Script suite SHALL create IAM roles with least-privilege policies for Lambda execution and SNS event destination
5. THE Provisioning_Script suite SHALL create CloudWatch log groups with a 30-day retention period for each Lambda function
6. THE Provisioning_Script suite SHALL create SQS DLQ queues with a message retention period of 14 days
7. THE Provisioning_Script suite SHALL output a summary of all created resource ARNs upon completion
8. THE Provisioning_Script suite SHALL be idempotent — running the script a second time SHALL detect existing resources and skip creation

### Requirement 9: Shared Libraries

**User Story:** As a developer, I want reusable shared modules for common operations, so that the Lambda handlers remain focused on business logic and share consistent behavior.

#### Acceptance Criteria

1. THE Social_Client_Wrapper SHALL wrap the `socialmessaging` boto3 client and provide methods for `send_message`, `upload_media`, `download_media`, `delete_media` with automatic retry (exponential backoff, max 3 attempts) on `ThrottledRequestException`
2. THE E164_Validator SHALL accept phone numbers in various formats (with/without `+`, with/without country code prefix, with spaces or dashes) and return a normalized E.164 string or raise a validation error
3. THE shared storage module SHALL provide CRUD functions for MessagesTable, ConversationsTable, ContactsTable, IdempotencyTable, and TemplatesTable with consistent error handling
4. THE shared config module SHALL read configuration from environment variables with fallback to AWS Systems Manager Parameter Store, supporting keys: `WABA_ID`, `ORIGINATION_PHONE_NUMBER_ID`, `SNS_TOPIC_ARN`, `TABLE_NAMES`, `REGION`, `LOG_LEVEL`, `S3_BUCKET_TEMPLATE_MEDIA`
5. THE shared event model module SHALL define the Normalized_Event dataclass with serialization to and from JSON

### Requirement 10: E.164 Phone Number Validation

**User Story:** As a developer, I want a robust phone number validation utility, so that all phone numbers stored and used in API calls conform to the E.164 international standard.

#### Acceptance Criteria

1. WHEN a phone number string is provided, THE E164_Validator SHALL strip all non-digit characters except the leading `+`
2. WHEN the resulting digits (after optional `+`) have a length between 7 and 15, THE E164_Validator SHALL return the number prefixed with `+`
3. IF the resulting digits have a length less than 7 or greater than 15, THEN THE E164_Validator SHALL raise a `ValidationError` with a descriptive message
4. WHEN a phone number is provided without a country code and a default country code is configured, THE E164_Validator SHALL prepend the default country code

### Requirement 11: Social Client Wrapper with Retry Logic

**User Story:** As a developer, I want the Social_Client_Wrapper to handle transient failures automatically, so that temporary throttling or network issues do not cause message delivery failures.

#### Acceptance Criteria

1. WHEN `SendWhatsAppMessage` raises `ThrottledRequestException`, THE Social_Client_Wrapper SHALL retry up to 3 times with exponential backoff (base delay 1 second, multiplier 2, jitter up to 500ms)
2. WHEN `PostWhatsAppMessageMedia` or `GetWhatsAppMessageMedia` raises `ThrottledRequestException`, THE Social_Client_Wrapper SHALL apply the same retry strategy
3. WHEN all retry attempts are exhausted, THE Social_Client_Wrapper SHALL raise the original exception to the caller
4. THE Social_Client_Wrapper SHALL log each retry attempt with the attempt number, delay, and operation name
5. THE Social_Client_Wrapper SHALL classify errors into `retryable` (ThrottledRequestException, connection errors) and `non_retryable` (ValidationException, AccessDeniedException) categories and only retry retryable errors

### Requirement 12: Normalized Event Model

**User Story:** As a developer, I want a canonical event model that normalizes the differences between SNS envelope formats and Meta webhook payload structures, so that downstream processing logic operates on a consistent schema.

#### Acceptance Criteria

1. THE Normalized_Event model SHALL contain fields: `event_id` (UUID), `event_type` (message | status | template_update | quality_update | account_update), `message_type` (text | image | video | audio | document | sticker | location | contacts | reaction | interactive | button | order | system | unsupported | request_welcome | ephemeral), `sender_phone`, `sender_name`, `recipient_phone`, `content`, `media_id`, `waba_id`, `phone_number_id`, `whatsapp_message_id`, `timestamp`, `raw_payload`
2. THE Normalized_Event model SHALL serialize to JSON and deserialize from JSON producing an equivalent object (round-trip property)
3. THE Normalized_Event model SHALL provide a `from_sns_event(sns_record)` factory method that parses the SNS_Event_Envelope and Meta_Webhook_Payload into one or more Normalized_Event instances
4. WHEN the `from_sns_event` method encounters an unrecognized message type, THE method SHALL set `message_type` to `unsupported` and include the raw type string in the `content` field

### Requirement 13: Testing and Fixtures

**User Story:** As a developer, I want unit tests with realistic SNS event fixtures, so that I can verify parsing, normalization, and storage logic without calling live AWS services.

#### Acceptance Criteria

1. THE test suite SHALL include fixture files containing realistic SNS_Event_Envelope JSON for each of the 18 message types, 4 status types, and 3 field-level event types
2. WHEN a fixture is loaded and passed to the `from_sns_event` factory method, THE resulting Normalized_Event SHALL have the correct `event_type`, `message_type`, `sender_phone`, and `content` fields
3. THE test suite SHALL include unit tests for the E164_Validator covering valid numbers, numbers with spaces/dashes, numbers without country code, and invalid numbers (too short, too long, non-numeric)
4. THE test suite SHALL include unit tests for the Social_Client_Wrapper retry logic using mocked boto3 clients that simulate `ThrottledRequestException` sequences
5. THE test suite SHALL include unit tests for the idempotency check logic verifying that duplicate events are skipped

### Requirement 14: Replay Tool

**User Story:** As a developer, I want a local replay tool that can feed saved SNS event fixtures into the Inbound_Handler, so that I can test and debug event processing without deploying to AWS.

#### Acceptance Criteria

1. WHEN invoked with a fixture file path, THE Replay_Tool SHALL read the JSON file, wrap it in an SNS event structure, and invoke the Inbound_Handler's `handler` function locally
2. WHEN invoked with a `--dry-run` flag, THE Replay_Tool SHALL parse and normalize the event but skip all DynamoDB writes and API calls, printing the Normalized_Event to stdout
3. THE Replay_Tool SHALL accept a `--fixture-dir` argument to replay all fixture files in a directory sequentially

### Requirement 15: Coverage Gap Matrix and Mapping Tables

**User Story:** As a system architect, I want comprehensive mapping tables and a coverage gap matrix, so that the team understands exactly which WhatsApp capabilities are available through AWS EUM Social and which require workarounds or are unavailable.

#### Acceptance Criteria

1. THE documentation SHALL include an AWS Mapping Table with columns: AWS API Operation → AWS Resource → Code Module → DynamoDB Item, covering all 21 AWS EUM Social API operations
2. THE documentation SHALL include a WhatsApp Capability Table with columns: Meta Capability → AWS EUM Social Equivalent → Gap Status (Full | Partial | None), covering all capability categories: Messaging (text, media, template, interactive, reaction, read receipt, location, contacts), Calling, Business Profile, Webhooks, Groups, Payments, Interactive Lists, Flows
3. THE documentation SHALL include an Event Crosswalk with columns: Meta Webhook Event → AWS SNS Event Field → Normalized_Event Field, covering all 26 webhook event types (18 message + 4 status + 1 payment + 3 field-level)
4. WHEN a Meta capability has no AWS EUM Social equivalent, THE Coverage_Gap_Matrix SHALL document the gap with severity (Critical | Medium | Low) and a recommended workaround

### Requirement 16: Operational Runbook

**User Story:** As a system operator, I want operational documentation covering throttling, DLQ management, alarms, security, and troubleshooting, so that the system can be monitored and maintained in production.

#### Acceptance Criteria

1. THE runbook SHALL document the AWS EUM Social API quotas: `SendWhatsAppMessage` 1000 req/sec, `PostWhatsAppMessageMedia` 100 req/sec, `GetWhatsAppMessageMedia` 100 req/sec, `DeleteWhatsAppMessageMedia` 100 req/sec
2. THE runbook SHALL document the DLQ monitoring procedure: how to check DLQ depth, how to replay failed messages, and how to investigate failures
3. THE runbook SHALL document the CloudWatch alarm configuration for: Lambda errors, DLQ depth threshold, API throttling rate
4. THE runbook SHALL document security practices: IAM least-privilege policies, SNS topic policy restrictions, S3 bucket policy for media, secrets management via Parameter Store or Secrets Manager
5. THE runbook SHALL document troubleshooting steps for common failure scenarios: SNS delivery failure, Lambda timeout, DynamoDB throttling, media download failure, invalid phone number format
