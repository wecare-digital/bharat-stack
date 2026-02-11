import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

/**
 * WECARE.DIGITAL DynamoDB Schema
 * 
 * 24 Tables with PAY_PER_REQUEST billing mode
 * TTL enabled on: Messages (30d), DLQMessages (7d), AuditLogs (180d), RateLimitTrackers (24h), VoiceCalls (90d), VoiceCDR (90d), AirtelSMS (90d), AirtelC2C (90d), OBDCampaign (90d)
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

  // Table 16: SmsAws - AWS Pinpoint SMS Messages (dedicated, TTL: 90 days)
  SmsAws: a
    .model({
      messageId: a.id().required(),
      contactId: a.string(),
      phoneNumber: a.string().required(),
      content: a.string().required(),
      direction: a.enum(['INBOUND', 'OUTBOUND']),
      status: a.string(), // SENT, DELIVERED, FAILED
      messageType: a.string(), // TRANSACTIONAL, PROMOTIONAL
      senderId: a.string(),
      providerMessageId: a.string(),
      campaignId: a.string(),
      campaignName: a.string(),
      errorDetails: a.string(),
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL
    })
    .identifier(['messageId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('phoneNumber'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 17: VoiceAws - AWS Pinpoint Voice Calls (dedicated, TTL: 90 days)
  VoiceAws: a
    .model({
      callId: a.id().required(),
      contactId: a.string(),
      phoneNumber: a.string().required(),
      direction: a.enum(['INBOUND', 'OUTBOUND']),
      callType: a.string(), // tts, audio
      status: a.string(), // initiated, completed, failed
      duration: a.integer().default(0),
      voiceId: a.string(),
      messageText: a.string(),
      providerCallId: a.string(),
      campaignId: a.string(),
      campaignName: a.string(),
      recordingUrl: a.string(),
      errorDetails: a.string(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
      expiresAt: a.integer(), // TTL
    })
    .identifier(['callId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('phoneNumber'),
    ])
    .authorization((allow) => [allow.authenticated()]),

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
      apiVersion: a.string(), // v4, v5, v6
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

  // Table 15b: DLTTemplates - DLT Template Registry for Airtel SMS
  DLTTemplates: a
    .model({
      templateId: a.id().required(),
      name: a.string().required(),
      content: a.string().required(),
      messageType: a.string(), // SERVICE_EXPLICIT, SERVICE_IMPLICIT, TRANSACTIONAL, PROMOTIONAL
      senderId: a.string().default('WDBEEP'),
      entityId: a.string().default('1201161991108627443'),
      variables: a.string().array(), // extracted {#var#} placeholders
      status: a.enum(['active', 'inactive']),
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['templateId'])
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
      callFlowId: a.string(), // Airtel call flow ID
      status: a.enum(['INITIATED', 'RINGING', 'CONNECTED', 'COMPLETED', 'FAILED', 'NO_ANSWER', 'BUSY']),
      duration: a.integer().default(0),
      recordingEnabled: a.boolean().default(true),
      recordingUrl: a.string(),
      s3RecordingKey: a.string(),
      correlationId: a.string(), // Airtel correlationId (Xchange ID)
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
      s3RecordingKey: a.string(),
      s3RecordingUrl: a.string(),
      
      // Retry info
      retryCountCaller: a.integer(),
      retryCountDestination: a.integer(),
      
      // Caller/Destination names (from participants)
      callerName: a.string(),
      destinationName: a.string(),
      
      // Caller duration & setup time
      callerDuration: a.integer(), // Total caller duration in ms
      callerDurationSec: a.float(),
      callSetupTimeCaller: a.integer(), // Call setup time in ms
      
      // Participants & Events (stored as JSON strings)
      participantsJson: a.string(), // Full participants array
      eventsJson: a.string(), // Full events array
      
      // Derived overall call status (per Airtel spec matrix)
      derivedOverallStatus: a.string(), // Computed from caller + destination status
      
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

  // Table 16: OBDCampaigns - Airtel OBD Campaign Records (TTL: 90 days)
  OBDCampaign: a
    .model({
      id: a.id().required(),
      campaignId: a.string(),
      airtelCampaignId: a.string(), // Airtel-assigned campaign ID
      campaignName: a.string().required(),
      status: a.string().default('created'), // created, running, completed, failed, DELETED
      audioUrl: a.string(),
      sheetFileNames: a.string(), // JSON array of uploaded CSV filenames
      contactCount: a.integer().default(0),
      createdAt: a.integer(),
      updatedAt: a.integer(),
      ttl: a.integer(), // TTL: Unix epoch seconds (90 days)
    })
    .identifier(['id'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 18: ScheduledMessages - Scheduled WhatsApp messages
  ScheduledMessage: a
    .model({
      scheduledId: a.id().required(),
      contactId: a.string().required(),
      contactName: a.string(),
      contactPhone: a.string(),
      templateName: a.string().required(),
      templateParams: a.string().array(), // template variable values
      phoneNumberId: a.string(),
      scheduledAt: a.datetime().required(),
      status: a.enum(['PENDING', 'SENT', 'FAILED', 'CANCELLED']),
      sentAt: a.datetime(),
      errorDetails: a.string(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
    })
    .identifier(['scheduledId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('status'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 19: WhatsAppVoice - WhatsApp TTS/Audio voice message logs (TTL: 90 days)
  WhatsAppVoice: a
    .model({
      messageId: a.id().required(),
      contactId: a.string(),
      phoneNumber: a.string(),
      messageText: a.string(),
      voiceId: a.string(), // Polly voice ID
      languageCode: a.string(),
      audioSize: a.integer(),
      s3Key: a.string(),
      whatsappMediaId: a.string(),
      whatsappMessageId: a.string(),
      status: a.string(), // sent, failed
      type: a.string().default('tts'), // tts, audio
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL
    })
    .identifier(['messageId'])
    .secondaryIndexes((index) => [
      index('contactId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 20: Payments - Razorpay payment records
  Payment: a
    .model({
      id: a.id().required(),
      paymentId: a.string(), // Razorpay payment ID
      orderId: a.string(), // Razorpay order ID
      referenceId: a.string(),
      status: a.string(), // captured, failed, refunded
      amount: a.integer(), // Amount in paise
      amountInRupees: a.float(),
      currency: a.string().default('INR'),
      method: a.string(), // upi, card, netbanking, wallet
      contact: a.string(),
      email: a.string(),
      notes: a.string(), // JSON string
      source: a.string().default('razorpay_webhook'),
      createdAt: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('paymentId'),
      index('orderId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 21: WhatsAppCalling - WhatsApp voice/video call logs
  WhatsAppCalling: a
    .model({
      id: a.id().required(),
      callId: a.string(),
      wabaId: a.string(),
      phoneNumberId: a.string(),
      fromNumber: a.string(),
      toNumber: a.string(),
      direction: a.string(), // inbound, outbound
      eventType: a.string(), // connect, terminate, permission_response
      status: a.string(), // ringing, ended, logged
      terminateReason: a.string(),
      duration: a.integer(),
      sdpOffer: a.string(),
      sdpType: a.string(),
      rawEvent: a.string(),
      timestamp: a.string(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('callId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 22: WhatsAppInbound - Inbound WhatsApp messages
  WhatsAppInbound: a
    .model({
      id: a.id().required(),
      contactId: a.string(),
      phone: a.string(),
      senderName: a.string(),
      messageType: a.string(), // text, image, video, audio, document, location, sticker, reaction
      content: a.string(),
      mediaId: a.string(),
      s3Key: a.string(),
      mediaUrl: a.string(),
      mimeType: a.string(),
      whatsappMessageId: a.string(),
      status: a.string(), // received, read, processed
      templateName: a.string(),
      timestamp: a.string(),
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('whatsappMessageId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 23: WhatsAppOutbound - Outbound WhatsApp messages
  WhatsAppOutbound: a
    .model({
      id: a.id().required(),
      contactId: a.string(),
      phone: a.string(),
      templateName: a.string(),
      templateCategory: a.string(), // UTILITY, MARKETING, AUTHENTICATION
      templateParams: a.string(), // JSON array
      content: a.string(),
      mediaId: a.string(),
      s3Key: a.string(),
      mediaUrl: a.string(),
      whatsappMessageId: a.string(),
      status: a.string(), // sent, delivered, read, failed
      errorDetails: a.string(),
      phoneNumberId: a.string(),
      timestamp: a.string(),
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('whatsappMessageId'),
      index('templateName'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 24: TemplateAnalytics - WhatsApp template send/delivery tracking
  TemplateAnalytics: a
    .model({
      id: a.id().required(),
      templateName: a.string().required(),
      templateCategory: a.string(), // UTILITY, MARKETING, AUTHENTICATION
      phone: a.string(),
      status: a.string(), // sent, delivered, read, failed
      whatsappMessageId: a.string(),
      timestamp: a.string(),
      createdAt: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('templateName'),
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
