import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

/**
 * WECARE.DIGITAL DynamoDB Schema
 * 
 * 13 Tables with PAY_PER_REQUEST billing mode
 * TTL enabled on: Messages (30d), DLQMessages (7d), AuditLogs (180d), RateLimitTrackers (24h), VoiceCalls (90d), VoiceCDR (90d)
 */
const schema = a.schema({
  // Table 1: Contacts - Contact records with opt-in preferences
  // Requirement 3.2: Default Block Rule - allowlist fields required
  Contact: a
    .model({
      contactId: a.id().required(),
      name: a.string(),
      phone: a.string(),
      email: a.string(),
      // Opt-in fields (Requirement 3.2: defaults to false)
      optInWhatsApp: a.boolean().default(false),
      optInSms: a.boolean().default(false),
      optInEmail: a.boolean().default(false),
      // Allowlist fields (Requirement 3.2: defaults to false)
      allowlistWhatsApp: a.boolean().default(false),
      allowlistSms: a.boolean().default(false),
      allowlistEmail: a.boolean().default(false),
      lastInboundMessageAt: a.datetime(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
      deletedAt: a.datetime(),
    })
    .identifier(['contactId'])
    .secondaryIndexes((index) => [
      index('phone'),
      index('email'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 2: Messages - All inbound/outbound messages (TTL: 30 days)
  Message: a
    .model({
      messageId: a.id().required(),
      contactId: a.string().required(),
      channel: a.enum(['WHATSAPP', 'SMS', 'EMAIL']),
      direction: a.enum(['INBOUND', 'OUTBOUND']),
      content: a.string(),
      timestamp: a.datetime(),
      status: a.enum(['PENDING', 'SENT', 'DELIVERED', 'READ', 'FAILED']),
      errorDetails: a.string(),
      whatsappMessageId: a.string(),
      mediaId: a.string(),
      s3Key: a.string(), // S3 storage location for media files
      mediaUrl: a.string(), // Pre-signed URL for media access
      senderPhone: a.string(), // Sender's phone number (inbound)
      senderName: a.string(), // Sender's WhatsApp profile name (inbound)
      receivingPhone: a.string(), // Receiving phone number (outbound)
      awsPhoneNumberId: a.string(), // WABA phone number ID
      expiresAt: a.integer(), // TTL: Unix epoch seconds (30 days)
    })
    .identifier(['messageId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('whatsappMessageId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 3: BulkJobs - Bulk messaging job tracking
  BulkJob: a
    .model({
      jobId: a.id().required(),
      createdBy: a.string().required(),
      channel: a.enum(['WHATSAPP', 'SMS', 'EMAIL']),
      totalRecipients: a.integer(),
      sentCount: a.integer().default(0),
      failedCount: a.integer().default(0),
      status: a.enum(['PENDING', 'IN_PROGRESS', 'PAUSED', 'COMPLETED', 'CANCELLED', 'FAILED']),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .identifier(['jobId'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 4: BulkRecipients - Individual recipient status per job
  BulkRecipient: a
    .model({
      jobId: a.string().required(),
      recipientId: a.string().required(),
      contactId: a.string().required(),
      status: a.enum(['PENDING', 'SENT', 'FAILED']),
      sentAt: a.datetime(),
      errorDetails: a.string(),
    })
    .identifier(['jobId', 'recipientId'])
    .authorization((allow) => [allow.authenticated()]),


  // Table 5: Users - Platform users with RBAC roles
  User: a
    .model({
      userId: a.id().required(),
      email: a.string().required(),
      role: a.enum(['VIEWER', 'OPERATOR', 'ADMIN']),
      createdAt: a.datetime(),
      lastLoginAt: a.datetime(),
    })
    .identifier(['userId'])
    .secondaryIndexes((index) => [index('email')])
    .authorization((allow) => [allow.authenticated()]),

  // Table 6: MediaFiles - WhatsApp media metadata
  MediaFile: a
    .model({
      fileId: a.id().required(),
      messageId: a.string().required(),
      s3Key: a.string().required(),
      contentType: a.string(),
      size: a.integer(),
      uploadedAt: a.datetime(),
      whatsappMediaId: a.string(),
    })
    .identifier(['fileId'])
    .secondaryIndexes((index) => [index('messageId')])
    .authorization((allow) => [allow.authenticated()]),

  // Table 7: DLQMessages - Failed message retry queue (TTL: 7 days)
  DLQMessage: a
    .model({
      dlqMessageId: a.id().required(),
      originalMessageId: a.string(),
      queueName: a.string().required(),
      retryCount: a.integer().default(0),
      lastAttemptAt: a.datetime(),
      payload: a.string(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (7 days)
    })
    .identifier(['dlqMessageId'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 8: AuditLogs - System audit trail (TTL: 180 days)
  AuditLog: a
    .model({
      logId: a.id().required(),
      userId: a.string(),
      action: a.string().required(),
      resourceType: a.string(),
      resourceId: a.string(),
      timestamp: a.datetime(),
      details: a.string(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (180 days)
    })
    .identifier(['logId'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 9: AIInteractions - AI query/response logs
  AIInteraction: a
    .model({
      interactionId: a.id().required(),
      messageId: a.string(),
      query: a.string(),
      response: a.string(),
      approved: a.boolean().default(false),
      feedback: a.string(),
      timestamp: a.datetime(),
    })
    .identifier(['interactionId'])
    .secondaryIndexes((index) => [index('messageId')])
    .authorization((allow) => [allow.authenticated()]),

  // Table 10: RateLimitTrackers - Rate limiting counters (TTL: 24 hours)
  RateLimitTracker: a
    .model({
      channel: a.string().required(),
      windowStart: a.string().required(),
      messageCount: a.integer().default(0),
      lastUpdatedAt: a.integer(), // TTL: Unix epoch seconds (24 hours)
    })
    .identifier(['channel', 'windowStart'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 11: SystemConfig - System configuration key-value store
  SystemConfig: a
    .model({
      configKey: a.string().required(),
      configValue: a.string(),
      updatedBy: a.string(),
      updatedAt: a.datetime(),
    })
    .identifier(['configKey'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 12: VoiceCalls - Voice call records (TTL: 90 days)
  VoiceCall: a
    .model({
      callId: a.id().required(),
      contactId: a.string(),
      phoneNumber: a.string().required(),
      provider: a.enum(['AWS', 'AIRTEL']),
      callType: a.enum(['TTS', 'AUDIO', 'IVR', 'CLICK_TO_CALL']),
      direction: a.enum(['INBOUND', 'OUTBOUND']),
      status: a.enum(['INITIATED', 'RINGING', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'NO_ANSWER', 'BUSY']),
      duration: a.integer().default(0),
      recordingUrl: a.string(),
      providerCallId: a.string(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (90 days)
    })
    .identifier(['callId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('phoneNumber'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 14: AirtelSMS - Airtel IQ SMS Messages (TTL: 90 days)
  // Sender ID: WDBEEP | Entity ID: 1201161991108627443
  AirtelSMS: a
    .model({
      messageId: a.id().required(),
      contactId: a.string(),
      phoneNumber: a.string().required(),
      content: a.string().required(),
      direction: a.enum(['INBOUND', 'OUTBOUND']),
      status: a.enum(['PENDING', 'SENT', 'DELIVERED', 'FAILED']),
      messageType: a.string(), // SERVICE_EXPLICIT, SERVICE_IMPLICIT, TRANSACTIONAL, PROMOTIONAL
      senderId: a.string().default('WDBEEP'),
      entityId: a.string().default('1201161991108627443'),
      dltTemplateId: a.string(),
      providerMessageId: a.string(),
      recipientCount: a.integer().default(1),
      errorDetails: a.string(),
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (90 days)
    })
    .identifier(['messageId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('phoneNumber'),
      index('status'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 15: AirtelC2C - Airtel Click-to-Call Records (TTL: 90 days)
  // Caller ID: 8047311032 | App ID: WECAREDIG_fD4BKqUbC8k90jNrPR0n
  AirtelC2C: a
    .model({
      callId: a.id().required(),
      contactId: a.string(),
      fromNumber: a.string().required(),
      toNumber: a.string().required(),
      callerId: a.string().default('8047311032'),
      status: a.enum(['INITIATED', 'RINGING', 'CONNECTED', 'COMPLETED', 'FAILED', 'NO_ANSWER', 'BUSY']),
      duration: a.integer().default(0),
      recordingEnabled: a.boolean().default(true),
      recordingUrl: a.string(),
      correlationId: a.string(), // Airtel call_id
      errorDetails: a.string(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (90 days)
    })
    .identifier(['callId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('fromNumber'),
      index('toNumber'),
      index('status'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 13: VoiceCDR - Airtel Voice CDR Records (TTL: 90 days)
  // Inbound Number: +91 9319767034 | Email: voice@wecare.digital
  VoiceCDR: a
    .model({
      id: a.id().required(),
      vmSessionId: a.string().required(), // Airtel unique session ID
      clientCorrelationId: a.string(), // Xchange ID for searching
      customerId: a.string(), // Customer name in Airtel system
      
      // Timestamps (epoch milliseconds from Airtel)
      startTime: a.integer(),
      endTime: a.integer(),
      callAnswerTime: a.integer(),
      timestamp: a.string(), // Airtel formatted timestamp
      
      // Duration fields (milliseconds)
      durationMs: a.integer(),
      durationSec: a.float(),
      fromWaitingTimeMs: a.integer(), // IVR wait time
      fromWaitingTimeSec: a.float(),
      conversationDurationMs: a.integer(), // Actual talk time
      conversationDurationSec: a.float(),
      billableDurationMs: a.integer(),
      billableDurationSec: a.float(),
      
      // Call details
      callType: a.enum(['INBOUND', 'OUTBOUND']),
      overallCallStatus: a.string(), // Answered, Missed, Disconnected, Busy
      hangupStatus: a.string(), // Party A, Party B, SYSTEM_INITIATED
      hangupCause: a.string(), // SYSTEM_INITIATED, USER_INITIATED
      
      // Phone numbers
      callerId: a.string(), // CLI number
      callerNumber: a.string(), // From number
      destinationNumber: a.string(), // To number
      calledNumber: a.string(), // Airtel VN for inbound
      displayCliDestination: a.string(),
      
      // Status details
      callerNumberStatus: a.string(), // Disconnected, NetworkError, NotReachable, Busy, Noanswer, Answer
      callerNumberStatusDetails: a.string(), // SIP code details
      destinationNumberStatus: a.string(),
      destinationNumberStatusDetails: a.string(),
      
      // Circle and operator info
      circleNameCaller: a.string(), // State name
      circleNameDestination: a.string(),
      operatorNameCaller: a.string(), // Bharti Airtel, Jio, etc.
      operatorNameDestination: a.string(),
      
      // Recording
      recordingURL: a.string(),
      
      // Retry info
      retryCountCaller: a.integer(),
      retryCountDestination: a.integer(),
      
      // Metadata
      participantsCount: a.integer(),
      source: a.string().default('airtel_cdr_webhook'),
      inboundNumber: a.string().default('+919319767034'),
      
      createdAt: a.integer(), // Unix epoch seconds
      expiresAt: a.integer(), // TTL: Unix epoch seconds (90 days)
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('vmSessionId'),
      index('callerNumber'),
      index('callType'),
    ])
    .authorization((allow) => [allow.authenticated()]),
});

export type Schema = ClientSchema<typeof schema>;

export const data = defineData({
  schema,
  authorizationModes: {
    defaultAuthorizationMode: 'userPool',
  },
  // DynamoDB billing mode: PAY_PER_REQUEST (on-demand)
});
