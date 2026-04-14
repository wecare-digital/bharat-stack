import { type ClientSchema, a, defineData } from '@aws-amplify/backend';

/**
 * WECARE.DIGITAL DynamoDB Schema
 * 
 * 41 Tables with PAY_PER_REQUEST billing mode
 * TTL enabled on: Messages (30d), DLQMessages (7d), AuditLogs (180d), RateLimitTrackers (24h), VoiceCalls (90d), VoiceCDR (90d), AirtelSMS (90d), AirtelC2C (90d), OBDCampaign (90d), RazorpayWebhookLog (180d), PayUWebhookLog (180d)
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
      // WhatsApp BSUID (Business-Scoped User ID) — unique per WABA portfolio
      // Format: CC.alphanumeric (e.g. "US.13491208655302741918")
      bsuid: a.string(),
      // Parent BSUID — for linked accounts (e.g. parent business account)
      parentBsuid: a.string(),
      // WhatsApp username (optional, user-set, e.g. "@pablomorales")
      username: a.string(),
      // Contact book name — auto-populated by Meta's contact book feature
      contactBookName: a.string(),
      // Opt-in fields (Requirement 3.2: defaults to false)
      optInWhatsApp: a.boolean().default(false),
      optInSms: a.boolean().default(false),
      optInEmail: a.boolean().default(false),
      // Allowlist fields (Requirement 3.2: defaults to false)
      allowlistWhatsApp: a.boolean().default(false),
      allowlistSms: a.boolean().default(false),
      allowlistEmail: a.boolean().default(false),
      lastInboundMessageAt: a.datetime(),
      // Address fields (enriched via flows)
      addressLine1: a.string(),
      addressLine2: a.string(),
      city: a.string(),
      state: a.string(),
      pincode: a.string(),
      country: a.string().default('IN'),
      // Structured address fields (WhatsApp Payments shipping_info)
      houseNumber: a.string(),
      buildingName: a.string(),
      towerNumber: a.string(),
      floorNumber: a.string(),
      landmark: a.string(),
      postalCode: a.string(),
      shippingAddress: a.string(),
      billingAddress: a.string(),
      shippingAddressJson: a.string(),
      billingAddressJson: a.string(),
      gstin: a.string(),
      // Business/profile fields (enriched via flows)
      companyName: a.string(),
      designation: a.string(),
      preferredLanguage: a.string(),
      isPep: a.boolean().default(false),
      pepDetails: a.string(),
      paidBy: a.string(), // self, company
      lastFlowInteractionAt: a.datetime(),
      satisfactionScore: a.integer(), // NPS/CSAT from feedback flows
      // Welcome message tracking
      welcomeSent: a.boolean(),
      welcomeSentAt: a.datetime(),
      tags: a.string().array(),
      createdAt: a.datetime(),
      updatedAt: a.datetime(),
      deletedAt: a.datetime(),
    })
    .identifier(['contactId'])
    .secondaryIndexes((index) => [
      index('phone'),
      index('email'),
      index('bsuid'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 2: Messages - All inbound/outbound messages (TTL: 30 days)
  Message: a
    .model({
      messageId: a.id().required(),
      contactId: a.string().required(),
      channel: a.enum(['WHATSAPP', 'SMS', 'EMAIL', 'RCS']),
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
      senderBsuid: a.string(), // Sender's BSUID (inbound)
      senderParentBsuid: a.string(), // Sender's parent BSUID (inbound, for linked accounts)
      senderUsername: a.string(), // Sender's WhatsApp username (inbound)
      receivingPhone: a.string(), // Receiving phone number (outbound)
      awsPhoneNumberId: a.string(), // WABA phone number ID
      transcription: a.string(), // English transcription of voice notes (audio messages)
      detectedLanguage: a.string(), // Detected language of voice note (e.g. "hi-IN", "en-US")
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
      channel: a.enum(['WHATSAPP', 'SMS', 'EMAIL', 'RCS']),
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
  // Caller ID: 8047311032 (Fixed Line · Karnataka) | App ID: WECAREDIG_fD4BKqUbC8k90jNrPR0n
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
  // Inbound Number: +91 9319767034 (Mobile · Delhi) | Email: voice@wecare.digital
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
      
      // Per-participant timing (epoch ms from participants array)
      callerStartTime: a.integer(),
      callerEndTime: a.integer(),
      callerAnswerTime: a.integer(),
      destStartTime: a.integer(),
      destEndTime: a.integer(),
      destAnswerTime: a.integer(),
      
      // Audio/IVR URLs (from participants array)
      callerAudioUrl: a.string(),
      destinationAudioUrl: a.string(),
      
      // OBD Campaign fields
      campaignId: a.string(),
      campaignName: a.string(),
      pulseCount: a.integer(), // Pulse count per Airtel spec
      dtmfCapture: a.string(), // DTMF capture
      missedDestinationNumber: a.string(), // Missed destination number
      
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
      recipientBsuid: a.string(), // Recipient's BSUID for BSUID-only sends
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
      recipientBsuid: a.string(), // Recipient's BSUID for voice messages
      messageText: a.string(),
      voiceId: a.string(), // Polly voice ID
      languageCode: a.string(),
      audioSize: a.integer(),
      s3Key: a.string(),
      whatsappMediaId: a.string(),
      whatsappMessageId: a.string(),
      status: a.string(), // sent, failed
      type: a.string().default('tts'), // tts, audio
      transcription: a.string(), // English transcription of voice note
      detectedLanguage: a.string(), // Detected source language
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
      displayPhone: a.string(), // Display phone number from webhook metadata
      fromNumber: a.string(),
      toNumber: a.string(),
      callerName: a.string(), // Caller's profile name from contacts array
      fromBsuid: a.string(), // Caller's BSUID (from webhook from_user_id / to_user_id)
      fromParentBsuid: a.string(), // Caller's parent BSUID (from webhook from_parent_user_id / to_parent_user_id)
      callerUsername: a.string(), // Caller's WhatsApp username
      direction: a.string(), // inbound, outbound
      eventType: a.string(), // connect, terminate, permission_response
      status: a.string(), // ringing, ended, logged
      terminateReason: a.string(),
      errorCode: a.string(), // Meta error code (138000-138023) from terminate events
      permission: a.string(), // GRANTED/REJECTED/REVOKED for permission events
      duration: a.integer(),
      sdpOffer: a.string(),
      sdpType: a.string(),
      apiResponse: a.string(), // Truncated API response for debugging
      rawEvent: a.string(),
      timestamp: a.string(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
      ttl: a.integer(), // TTL: Unix epoch seconds (90 days)
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('callId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 22: WhatsAppGroup - WhatsApp Business group tracking
  WhatsAppGroup: a
    .model({
      id: a.id().required(),
      groupId: a.string().required(), // Meta group ID
      wabaId: a.string(),
      phoneNumberId: a.string(),
      subject: a.string(),
      description: a.string(),
      inviteLink: a.string(),
      joinApprovalMode: a.string(), // auto_approve | approval_required
      participantCount: a.integer().default(0),
      maxParticipants: a.integer().default(512),
      owner: a.string(),
      suspended: a.boolean().default(false),
      createdAt: a.integer(),
      updatedAt: a.integer(),
      ttl: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('groupId'),
      index('wabaId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 23: WhatsAppInbound - Inbound WhatsApp messages
  WhatsAppInbound: a
    .model({
      id: a.id().required(),
      contactId: a.string(),
      phone: a.string(),
      senderName: a.string(),
      senderBsuid: a.string(), // Sender's BSUID (from webhook user_id)
      senderParentBsuid: a.string(), // Sender's parent BSUID (from webhook parent_user_id)
      senderUsername: a.string(), // Sender's WhatsApp username (from webhook)
      messageType: a.string(), // text, image, video, audio, document, location, sticker, reaction
      content: a.string(),
      mediaId: a.string(),
      s3Key: a.string(),
      mediaUrl: a.string(),
      mimeType: a.string(),
      whatsappMessageId: a.string(),
      status: a.string(), // received, read, processed
      templateName: a.string(),
      transcription: a.string(), // English transcription of inbound voice notes
      detectedLanguage: a.string(), // Detected language of voice note
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
      recipientBsuid: a.string(), // Recipient's BSUID (when sending to BSUID)
      parentRecipientBsuid: a.string(), // Recipient's parent BSUID (from status webhooks)
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
      transcription: a.string(), // English transcription of outbound voice notes
      detectedLanguage: a.string(), // Language of outbound voice note
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

  // Table 25: WixProductsCache - Cached Wix Store products
  WixProductsCache: a
    .model({
      productId: a.id().required(),
      name: a.string(),
      slug: a.string(),
      price: a.string(),
      currency: a.string(),
      inStock: a.boolean(),
      productType: a.string(),
      mediaUrl: a.string(),
      rawData: a.string(), // Full Wix product JSON
      syncedAt: a.datetime(),
    })
    .identifier(['productId'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 26: WixOrdersCache - Cached Wix Store orders
  WixOrdersCache: a
    .model({
      orderId: a.id().required(),
      orderNumber: a.string(),
      externalOrderId: a.string(), // Custom order number from external channel
      buyerEmail: a.string(),
      buyerPhone: a.string(),
      totalPrice: a.string(),
      currency: a.string(),
      paymentStatus: a.string(),
      fulfillmentStatus: a.string(),
      status: a.string(), // APPROVED, CANCELED, etc.
      lineItemCount: a.integer(),
      createdDate: a.string(),
      rawData: a.string(), // Full Wix order JSON
      syncedAt: a.datetime(),
    })
    .identifier(['orderId'])
    .secondaryIndexes((index) => [
      index('buyerEmail'),
      index('paymentStatus'),
      index('orderNumber'),
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
  // Table 27: SubmitRequests - WhatsApp Flow submit request submissions
  SubmitRequest: a
    .model({
      id: a.id().required(),
      requestId: a.string().required(), // Lambda request ID
      flowToken: a.string(),
      phone: a.string().required(),
      senderName: a.string(),
      contactId: a.string(),
      orderId: a.string().required(),
      subject: a.string(),
      description: a.string(),
      paymentStatus: a.string().default('pending'), // pending, captured, failed
      paymentReferenceId: a.string(), // SR-{orderId}-{requestId}
      paymentAmount: a.integer().default(4900), // paise
      transactionId: a.string(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('phone'),
      index('orderId'),
      index('paymentStatus'),
      index('paymentReferenceId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 28: ConversationHistory - AI conversation context per phone hash
  ConversationHistory: a
    .model({
      phoneHash: a.string().required(),
      lastMessage: a.string(),
      lastResponse: a.string(),
      pendingPaymentRef: a.string(),
      customerProfile: a.string(), // JSON string
      languagePreference: a.string(),
      autoReplyEnabled: a.boolean().default(true),
      updatedAt: a.integer(),
    })
    .identifier(['phoneHash'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 29: WixOrderIds - Mapping between Wix order IDs and WD-ORD numbers
  WixOrderId: a
    .model({
      wixOrderId: a.string().required(),
      wdOrderNumber: a.string().required(),
      createdAt: a.integer(),
    })
    .identifier(['wixOrderId'])
    .secondaryIndexes((index) => [
      index('wdOrderNumber'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 30: Invoice - Invoice records
  Invoice: a
    .model({
      invoiceId: a.id().required(),
      invoiceNumber: a.string(),
      contactId: a.string(),
      contactName: a.string(),
      contactPhone: a.string(),
      contactEmail: a.string(),
      // Customer fields (used by invoice-engine Lambda)
      customerName: a.string(),
      customerPhone: a.string(),
      paidByPhone: a.string(),
      customerEmail: a.string(),
      shippingAddress: a.string(),
      billingAddress: a.string(),
      gstin: a.string(),
      status: a.string().default('created'), // created, pending_payment, sent, paid, cancelled
      paymentStatus: a.string().default('pending'), // pending, captured, failed, refunded
      entryPoint: a.string(), // manual, pay_flow, whatsapp_payment, webhook
      subtotal: a.integer(), // paise
      taxAmount: a.integer(),
      tax: a.float(), // rupees (used by invoice-engine)
      totalAmount: a.integer(),
      total: a.float(), // rupees (used by invoice-engine)
      discount: a.float(),
      shipping: a.float(),
      handling: a.float(),
      gstRate: a.float(),
      convenienceFee: a.float(),
      currency: a.string().default('INR'),
      referenceId: a.string(), // payment reference
      paymentId: a.string(), // Razorpay payment ID
      orderId: a.string(),
      purpose: a.string(),
      notes: a.string(),
      remarks: a.string(), // JSON array of remarks/refunds/credit notes
      imageUrl: a.string(),
      pdfUrl: a.string(),
      s3Key: a.string(),
      fy: a.string(), // financial year
      paidAt: a.integer(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['invoiceId'])
    .secondaryIndexes((index) => [
      index('contactId'),
      index('referenceId'),
      index('status'),
      index('invoiceNumber'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 31: InvoiceItem - Line items per invoice
  InvoiceItem: a
    .model({
      invoiceId: a.string().required(),
      itemId: a.string().required(),
      description: a.string(),
      quantity: a.integer().default(1),
      unitPrice: a.integer(), // paise
      amount: a.integer(), // paise
      hsnCode: a.string(),
      gstRate: a.float(),
    })
    .identifier(['invoiceId', 'itemId'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 32: InvoiceAsset - Generated invoice images/PDFs
  InvoiceAsset: a
    .model({
      assetId: a.id().required(),
      invoiceId: a.string().required(),
      assetType: a.string(), // image, pdf
      s3Key: a.string(),
      url: a.string(),
      createdAt: a.integer(),
    })
    .identifier(['assetId'])
    .secondaryIndexes((index) => [
      index('invoiceId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 33: InvoiceDeliveryLog - Invoice delivery tracking
  InvoiceDeliveryLog: a
    .model({
      id: a.id().required(),
      invoiceId: a.string().required(),
      channel: a.string(), // whatsapp, email
      status: a.string(), // sent, delivered, failed
      recipient: a.string(),
      waMessageId: a.string(),
      createdAt: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('invoiceId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 34: InvoiceSequence - Auto-increment invoice number tracking per FY
  InvoiceSequence: a
    .model({
      fy: a.string().required(), // e.g. "2025-26"
      lastSeq: a.integer().default(0),
      updatedAt: a.integer(),
    })
    .identifier(['fy'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 35: RazorpayWebhookLog - Raw Razorpay webhook event log
  RazorpayWebhookLog: a
    .model({
      id: a.id().required(),
      eventType: a.string(), // payment.captured, payment.failed, etc.
      paymentId: a.string(),
      orderId: a.string(),
      amount: a.integer(),
      status: a.string(),
      rawPayload: a.string(), // JSON string
      razorpayEventId: a.string(), // Idempotency key
      processedAt: a.integer(),
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (180 days)
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('paymentId'),
      index('eventType'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 36: PayUWebhookLog - Raw PayU webhook event log
  PayUWebhookLog: a
    .model({
      id: a.id().required(),
      eventType: a.string(), // payment.success, payment.failed, etc.
      paymentId: a.string(), // mihpayid
      txnId: a.string(),
      amount: a.float(),
      status: a.string(),
      mode: a.string(), // CC, DC, NB, UPI, WALLET
      phone: a.string(),
      email: a.string(),
      bankRef: a.string(),
      rawPayload: a.string(), // JSON string
      processedAt: a.integer(),
      createdAt: a.integer(),
      expiresAt: a.integer(), // TTL: Unix epoch seconds (180 days)
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('paymentId'),
      index('txnId'),
      index('eventType'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 37: WhatsAppGroup - WhatsApp Groups state tracking
  WhatsAppGroup: a
    .model({
      id: a.id().required(),
      groupId: a.string().required(), // Meta group ID
      wabaId: a.string(),
      phoneNumberId: a.string(),
      subject: a.string(), // Group name/subject
      description: a.string(),
      creatorPhone: a.string(),
      participantCount: a.integer().default(0),
      participantsJson: a.string(), // JSON array of participants
      status: a.string().default('active'), // active, archived, deleted
      lastMessageAt: a.integer(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('groupId'),
      index('wabaId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 38: WebhookDedup - Webhook idempotency tracking for inbound events
  WebhookDedup: a
    .model({
      eventId: a.string().required(), // Unique event identifier
      source: a.string().required(), // whatsapp, razorpay, payu
      processedAt: a.integer(),
      expiresAt: a.integer(), // TTL: 7 days
      ttl: a.integer(), // TTL attribute for backend.ts override
    })
    .identifier(['eventId'])
    .authorization((allow) => [allow.authenticated()]),

  // Table 39: SystemEvent - Persistent system event log (template status, quality, account updates)
  SystemEvent: a
    .model({
      id: a.id().required(),
      eventType: a.string().required(), // template_status, phone_quality, account_update, user_id_update
      wabaId: a.string(),
      phoneNumberId: a.string(),
      eventData: a.string(), // JSON string
      severity: a.string().default('info'), // info, warning, error, critical
      acknowledged: a.boolean().default(false),
      createdAt: a.integer(),
      ttl: a.integer(), // TTL: 180 days
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('eventType'),
      index('wabaId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 40: CatalogCache - WhatsApp Commerce catalog product cache
  CatalogCache: a
    .model({
      id: a.id().required(),
      catalogId: a.string().required(),
      retailerId: a.string(), // Retailer/product ID
      name: a.string(),
      description: a.string(),
      price: a.string(),
      currency: a.string(),
      imageUrl: a.string(),
      availability: a.string(), // in_stock, out_of_stock
      rawData: a.string(), // Full product JSON
      syncedAt: a.integer(),
      ttl: a.integer(), // TTL: 7 days (cache refresh)
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('catalogId'),
      index('retailerId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table 41: AdClickAttribution - Ads that Click to WhatsApp tracking
  AdClickAttribution: a
    .model({
      id: a.id().required(),
      adId: a.string(),
      campaignId: a.string(),
      referralSource: a.string(), // ctwa (click-to-whatsapp)
      referralBody: a.string(), // Referral message body
      referralUrl: a.string(), // Source URL
      senderPhone: a.string(),
      contactId: a.string(),
      convertedAt: a.integer(), // When user performed target action
      conversionType: a.string(), // message_sent, purchase, signup
      createdAt: a.integer(),
      ttl: a.integer(), // TTL: 180 days
    })
    .identifier(['id'])
    .secondaryIndexes((index) => [
      index('adId'),
      index('contactId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // ============================================================
  // FLOW MANAGEMENT TABLES
  // ============================================================

  // Table: FlowRegistry — Config for every WhatsApp Flow
  FlowRegistry: a
    .model({
      flowId: a.id().required(), // Meta flow ID
      flowCode: a.string().required(), // "01.WD_SR", "02.WD_ADDR", etc.
      flowName: a.string().required(), // Human readable
      flowType: a.string().required(), // form_submit, order_management, interactive, data_collection, payment, booking, feedback
      flowVersion: a.string(), // "7.3"
      dataApiVersion: a.string(), // "4.0"
      wabaId: a.string(), // Which WABA
      status: a.string().default('DRAFT'), // DRAFT, PUBLISHED, DEPRECATED
      category: a.string(), // service_request, order, interactive, data_collection, payment, booking, feedback
      // Payment config
      requiresPayment: a.boolean().default(false),
      paymentAmount: a.integer(), // paise (4900 = ₹49)
      paymentDescription: a.string(),
      // Payment gateway preference: 'razorpay' or 'payu' (used when sending native payment)
      preferredGateway: a.string(),
      // Specific Meta payment config name (e.g. 'WECARE-RAZOR-PAY', 'PayU_ManishAgarwal')
      paymentConfigName: a.string(),
      // Screen routing config (JSON string)
      screenConfig: a.string(),
      // Contact enrichment mapping (JSON string) e.g. {"address_line1":"addressLine1","city":"city"}
      contactMapping: a.string(),
      // Data fetchers config (JSON string) — which screens need backend data
      dataFetchers: a.string(),
      // Submission number prefix e.g. "WD-SR", "WD-RET", "WD-BK"
      submissionPrefix: a.string(),
      // A/B testing config (JSON) e.g. {"enabled":true,"variantB_flowId":"xxx","splitPercent":50}
      abTestConfig: a.string(),
      // Metadata
      endpointUri: a.string(),
      publishedAt: a.integer(),
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['flowId'])
    .secondaryIndexes((index) => [
      index('flowCode'),
      index('wabaId'),
      index('category'),
      index('status'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // ============================================================
  // ORDER MANAGEMENT TABLES
  // ============================================================

  // Table: Order — Central order repository (all sources: Wix, manual, Shopify, future)
  Order: a
    .model({
      orderId: a.string().required(), // "WD-ORD-A1B2C3D4" — canonical full ID
      shortId: a.string().required(), // "A1B2C3D4" — 8-char hex for display
      // Source
      source: a.string().required(), // wix | manual | shopify | woocommerce | custom
      sourceOrderId: a.string(), // native ID from source store (e.g. Wix UUID)
      sourceOrderNumber: a.string(), // native display number (e.g. "10042") — internal only
      sourceRawPayload: a.string(), // JSON of raw source data for audit
      // Customer
      customerPhone: a.string().required(),
      customerName: a.string(),
      customerEmail: a.string(),
      contactId: a.string(), // link to ContactsTable
      // Order details
      orderDate: a.string(), // ISO date "2026-02-22"
      orderTime: a.string(), // "18:00:00"
      orderDateIST: a.string(), // "22 Feb 2026, 6:00 PM" — pre-formatted for dropdown
      itemsSummary: a.string(), // "Black Tee × 1, White Cap × 2"
      itemsJson: a.string(), // JSON array [{name, qty, price, sku, image}]
      itemCount: a.integer(),
      totalAmount: a.float(), // rupees (not paise)
      subtotal: a.float(),
      shippingAmount: a.float(),
      taxAmount: a.float(),
      discountAmount: a.float(),
      currency: a.string().default('INR'),
      // Status
      orderStatus: a.string().default('active'), // active | fulfilled | cancelled | returned
      paymentStatus: a.string().default('pending'), // paid | not_paid | pending | refunded
      fulfillmentStatus: a.string(), // not_fulfilled | partially_fulfilled | fulfilled
      // Address
      shippingAddress: a.string(), // JSON or flat string
      billingAddress: a.string(),
      // Metadata
      buyerNote: a.string(),
      adminNotes: a.string(),
      tags: a.string(), // JSON array of tags
      // Timestamps
      createdAt: a.integer(),
      updatedAt: a.integer(),
      syncedAt: a.integer(), // last sync from source
    })
    .identifier(['orderId'])
    .secondaryIndexes((index) => [
      index('customerPhone'),
      index('source'),
      index('orderStatus'),
      index('shortId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table: RequestStatusHistory — Audit trail for request status changes
  RequestStatusHistory: a
    .model({
      historyId: a.id().required(),
      submissionId: a.string().required(), // link to FlowSubmission
      orderId: a.string(), // link to Order
      oldStatus: a.string(),
      newStatus: a.string(),
      changedBy: a.string(), // "admin:userId" | "system" | "webhook"
      changedByName: a.string(),
      notes: a.string(),
      changedAt: a.integer(),
    })
    .identifier(['historyId'])
    .secondaryIndexes((index) => [
      index('submissionId'),
      index('orderId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table: FlowSubmission — All flow submissions (generic, all flow types)
  FlowSubmission: a
    .model({
      submissionId: a.id().required(),
      flowId: a.string().required(), // Meta flow ID
      flowCode: a.string().required(), // "01.WD_SR"
      flowType: a.string(), // form_submit, order_management, etc.
      flowVersion: a.string(), // "7.3"
      // Who
      phone: a.string().required(),
      contactId: a.string(),
      senderName: a.string(),
      // What — full form data as JSON
      formData: a.string(), // JSON string of all form fields
      // Extracted common fields for querying
      orderId: a.string(),
      requestType: a.string(),
      subject: a.string(),
      description: a.string(),
      // Reference numbers
      submissionNumber: a.string(), // "WD-SR-A1B2C3D4"
      flowToken: a.string(),
      // Payment tracking
      paymentRequired: a.boolean().default(false),
      paymentAmount: a.integer(), // paise
      paymentStatus: a.string().default('none'), // none, pending, captured, failed, refunded
      paymentRefId: a.string(), // "WD-PAY-XXXXXXXX"
      invoiceId: a.string(),
      transactionId: a.string(), // Payment gateway txn ID
      paidAt: a.integer(),
      // Lifecycle
      status: a.string().default('open'), // open, in_progress, resolved, closed, cancelled
      assignedTo: a.string(),
      notes: a.string(),
      resolvedAt: a.integer(),
      // Timestamps
      createdAt: a.integer(),
      updatedAt: a.integer(),
    })
    .identifier(['submissionId'])
    .secondaryIndexes((index) => [
      index('phone'),
      index('flowCode'),
      index('paymentStatus'),
      index('paymentRefId'),
      index('submissionNumber'),
      index('status'),
      index('orderId'),
      index('flowId'),
    ])
    .authorization((allow) => [allow.authenticated()]),

  // Table: FlowLog — Audit trail for every flow screen interaction
  FlowLog: a
    .model({
      logId: a.id().required(),
      flowId: a.string(),
      flowCode: a.string(),
      flowToken: a.string(),
      phone: a.string(),
      action: a.string(), // INIT, data_exchange, navigate, complete, ping
      screen: a.string(),
      dataSnapshot: a.string(), // JSON of data exchanged
      requestId: a.string(), // Lambda request ID
      isError: a.boolean().default(false),
      errorType: a.string(),
      errorMessage: a.string(),
      createdAt: a.integer(),
      ttl: a.integer(), // TTL: 90 days
    })
    .identifier(['logId'])
    .secondaryIndexes((index) => [
      index('phone'),
      index('flowId'),
      index('flowCode'),
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
}) as any;
