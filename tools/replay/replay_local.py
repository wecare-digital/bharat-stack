#!/usr/bin/env python3
"""
Local replay tool: ingest saved SNS event JSON → normalize → optionally write to DynamoDB.
Usage: python replay_local.py <fixture_file.json> [--dry-run]
"""
import sys
import json
import argparse
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


def extract_content(message: dict) -> str:
    msg_type = message.get('type', '')
    if msg_type == 'text':
        return message.get('text', {}).get('body', '')
    elif msg_type in ('image', 'video', 'document'):
        return message.get(msg_type, {}).get('caption', f'[{msg_type.title()}]')
    elif msg_type == 'location':
        loc = message.get('location', {})
        return f"[Location: {loc.get('latitude')}, {loc.get('longitude')}]"
    elif msg_type == 'reaction':
        return message.get('reaction', {}).get('emoji', '')
    return f'[{msg_type}]'


def replay_event(fixture_path: str, dry_run: bool = False):
    with open(fixture_path, 'r') as f:
        event = json.load(f)

    records = event.get('Records', [])
    logger.info(f"Replaying {len(records)} record(s) from {fixture_path}")

    for record in records:
        sns_message = json.loads(record.get('Sns', {}).get('Message', '{}'))
        webhook_entry = json.loads(sns_message.get('whatsAppWebhookEntry', '{}'))
        context = sns_message.get('context', {})

        logger.info(f"  WABA IDs: {context.get('MetaWabaIds', [])}")

        for change in webhook_entry.get('changes', []):
            value = change.get('value', {})
            field = change.get('field', 'messages')

            for msg in value.get('messages', []):
                content = extract_content(msg)
                logger.info(f"  MSG type={msg.get('type')} from={msg.get('from')} id={msg.get('id')}")
                logger.info(f"      content={content[:100]}")

            for status in value.get('statuses', []):
                logger.info(f"  STATUS {status.get('status')} id={status.get('id')} recipient={status.get('recipient_id')}")

            if field != 'messages':
                logger.info(f"  EVENT field={field} data={json.dumps(value)[:200]}")

    logger.info("Replay complete" + (" (dry-run)" if dry_run else ""))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Replay SNS event fixtures locally')
    parser.add_argument('fixture', help='Path to SNS event JSON fixture file')
    parser.add_argument('--dry-run', action='store_true', help='Parse only, do not write to DynamoDB')
    args = parser.parse_args()
    replay_event(args.fixture, args.dry_run)
