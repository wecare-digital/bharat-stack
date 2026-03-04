# Data Management Tools - Internal Agent

## Overview

The internal agent now includes powerful data management and cleanup tools for maintaining your CRM data.

## New Capabilities (6 Tools)

### 1. Add Contact Email
**Tool**: `add_contact_email`

**Usage Examples:**
```
"add email john@example.com to Jignesh"
"update Jignesh's email to new@email.com"
"set email for contact Jignesh"
```

**What it does:**
- Adds or updates email address for a contact
- Automatically finds contact by name
- Updates contact record in DynamoDB

---

### 2. Delete Contact
**Tool**: `delete_contact`

**Usage Examples:**
```
"delete contact Jignesh"
"remove Jignesh from contacts"
"soft delete contact Jignesh"
```

**What it does:**
- Soft deletes contact (marks as deleted, doesn't remove data)
- Contact won't appear in searches
- Data remains for recovery if needed

---

### 3. Delete Messages
**Tool**: `delete_messages`

**Usage Examples:**
```
"delete all messages from Jignesh"
"remove messages for Jignesh"
"delete inbound messages from Jignesh"
"delete outbound messages to Jignesh"
"clear message history for Jignesh"
```

**What it does:**
- Deletes specific messages or all messages for a contact
- Can filter by direction (inbound/outbound/all)
- Removes from DynamoDB messages table

---

### 4. Delete Media Files
**Tool**: `delete_media_files`

**Usage Examples:**
```
"delete all media files for Jignesh"
"remove S3 files for Jignesh"
"clear images for Jignesh"
"delete videos from Jignesh"
```

**What it does:**
- Deletes media files (images, videos, audio, documents) from S3
- Can delete specific files or all files for a contact
- Frees up S3 storage space

---

### 5. List Media Files
**Tool**: `list_media_files`

**Usage Examples:**
```
"list all media files for Jignesh"
"show images for Jignesh"
"what files do we have for Jignesh"
"list videos from Jignesh"
```

**What it does:**
- Lists all media files stored in S3 for a contact
- Shows file type, size, and last modified date
- Can filter by type (image/video/audio/document)

---

### 6. Clear All Contact Data (DANGEROUS)
**Tool**: `clear_all_contact_data`

**Usage Examples:**
```
"clear all data for Jignesh"
"completely delete everything for Jignesh"
"purge all Jignesh data"
```

**What it does:**
- **COMPLETELY REMOVES ALL DATA** for a contact:
  - All messages (inbound + outbound)
  - All media files from S3
  - Conversation history
  - Contact record (soft delete)
- Requires explicit confirmation
- Cannot be undone!

**⚠️ WARNING**: This is a destructive operation. Use with extreme caution!

---

## Safety Features

### Confirmation Required
For dangerous operations like `clear_all_contact_data`, the AI will:
1. Ask for confirmation first
2. Explain what will be deleted
3. Require explicit "yes" or "confirm" from user

### Soft Deletes
- Contact deletion is "soft" (marks as deleted)
- Data remains in database for recovery
- Can be restored if needed

### Logging
All data management operations are logged with:
- Timestamp
- Contact ID
- Operation type
- Items affected
- Request ID for tracing

---

## Example Workflows

### Clean Up Old Contact
```
User: "I want to clean up data for old contact Jignesh"
AI: "I can help with that. What would you like to do?"
User: "Delete all messages and media files"
AI: [Searches for Jignesh] → [Deletes messages] → [Deletes media]
AI: "Done! Deleted 45 messages and 12 media files for Jignesh Ashar."
```

### Add Missing Email
```
User: "add email jignesh@example.com to Jignesh"
AI: [Searches for Jignesh] → [Updates email]
AI: "Email jignesh@example.com added to Jignesh Ashar's contact."
```

### Complete Data Purge
```
User: "completely delete all data for test contact"
AI: "This will delete ALL data including messages, media files, and conversation history. Are you sure?"
User: "yes, confirm"
AI: [Executes clear_all_contact_data]
AI: "Cleared all data: 23 messages, 5 media files, conversation history, and contact record."
```

### List Media Before Deletion
```
User: "show me all media files for Jignesh"
AI: [Lists media files]
AI: "Found 8 media files: 5 images (2.3 MB), 2 videos (15.7 MB), 1 document (0.5 MB)"
User: "delete all videos"
AI: [Deletes video files]
AI: "Deleted 2 video files (15.7 MB freed)."
```

---

## Best Practices

### 1. Check Before Deleting
Always list or review data before deletion:
```
"show messages from Jignesh" → Review → "delete all messages"
```

### 2. Use Specific Filters
Be specific about what to delete:
```
"delete inbound messages from Jignesh" (not all messages)
"delete images for Jignesh" (not all media)
```

### 3. Backup Important Data
Before bulk deletion:
1. Export data if needed
2. Verify contact information
3. Confirm with team if necessary

### 4. Test with Test Contacts
Practice data management on test contacts first:
```
"create test contact named TestUser"
"add test data"
"practice deletion"
```

---

## Permissions & Security

### Required Permissions
The Lambda function needs:
- DynamoDB: Read, Write, Delete on Contacts, Messages, Conversation tables
- S3: ListBucket, GetObject, DeleteObject on media bucket

### Audit Trail
All operations are logged to CloudWatch:
- `/aws/lambda/wecare-ai-generate-response`
- Search for: `contact_deleted`, `messages_deleted`, `media_files_deleted`, `all_contact_data_cleared`

### Rate Limiting
Consider implementing rate limits for:
- Bulk deletions
- Multiple contact operations
- S3 file deletions

---

## Troubleshooting

### "Contact not found"
- Verify contact name spelling
- Try searching first: "find contact Jignesh"
- Use phone number if name is ambiguous

### "Permission denied"
- Check Lambda IAM role permissions
- Verify DynamoDB table access
- Confirm S3 bucket permissions

### "Partial deletion"
- Some items may fail to delete
- Check CloudWatch logs for details
- Retry operation if needed

---

## Future Enhancements

Planned features:
- Bulk contact operations
- Data export before deletion
- Scheduled cleanup jobs
- Retention policy enforcement
- Restore deleted contacts
- Archive instead of delete
- Data anonymization

---

## API Reference

### Tool Schemas

```python
# Add Contact Email
{
    'contactId': 'string',
    'email': 'string'
}

# Delete Contact
{
    'contactId': 'string'
}

# Delete Messages
{
    'contactId': 'string',
    'messageIds': ['string'],  # Optional
    'direction': 'inbound|outbound|all'  # Optional
}

# Delete Media Files
{
    'contactId': 'string',
    'fileKeys': ['string']  # Optional
}

# Clear All Contact Data
{
    'contactId': 'string',
    'confirm': true  # Required
}

# List Media Files
{
    'contactId': 'string',
    'fileType': 'image|video|audio|document|all'  # Optional
}
```

---

**Version**: 1.0.0  
**Last Updated**: March 3, 2026  
**Status**: Production Ready ✅
