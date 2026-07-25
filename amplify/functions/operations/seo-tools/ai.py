"""Bedrock model invocation and compact SEO prompts."""
import json
import os
from typing import Any, Dict

import boto3

REGION = os.environ.get('AWS_REGION', 'us-east-1')
PRIMARY_MODEL = os.environ.get(
    'BEDROCK_MODEL_ID', 'global.anthropic.claude-sonnet-4-6'
)
MODEL_CHAIN = [
    PRIMARY_MODEL,
    'global.anthropic.claude-opus-4-6-v1',
    'amazon.nova-pro-v1:0',
]
_client = None

SEO_FIELDS = """Return only JSON with: seoTitle, metaDescription, focusKeyword,
secondaryKeywords (9), jsonLd, metaTags, internalLinks, imageAltText,
seoScoreBefore, seoScoreAfter, scoreBreakdown, warnings, confidence.
Titles must be at most 60 characters and descriptions 120-160 characters.
Use en-IN, https://www.wecare.digital URLs, and factual source content only."""


def client():
    global _client
    if _client is None:
        _client = boto3.client('bedrock-runtime', region_name=REGION)
    return _client


def _request(model_id: str, system: str, message: str) -> Dict[str, Any]:
    if 'nova' in model_id:
        return {
            'schemaVersion': 'messages-v1',
            'system': [{'text': system}],
            'messages': [{'role': 'user', 'content': [{'text': message}]}],
            'inferenceConfig': {'max_new_tokens': 4096, 'temperature': 0.3},
        }
    return {
        'anthropic_version': 'bedrock-2023-05-31',
        'max_tokens': 4096,
        'temperature': 0.3,
        'system': system,
        'messages': [{'role': 'user', 'content': message}],
    }


def _parse(model_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    if 'nova' in model_id:
        text = payload.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '')
        usage = payload.get('usage', {})
        return {
            'text': text,
            'inputTokens': usage.get('inputTokens', 0),
            'outputTokens': usage.get('outputTokens', 0),
        }
    usage = payload.get('usage', {})
    return {
        'text': payload.get('content', [{}])[0].get('text', ''),
        'inputTokens': usage.get('input_tokens', 0),
        'outputTokens': usage.get('output_tokens', 0),
    }


def parse_json(text: str) -> Dict[str, Any]:
    clean = text.strip()
    if clean.startswith('```'):
        clean = clean.split('\n', 1)[-1]
        if clean.endswith('```'):
            clean = clean[:-3]
    value = json.loads(clean.strip())
    if not isinstance(value, dict):
        raise ValueError('AI response must be a JSON object')
    return value


def invoke_seo(page: Dict[str, Any], page_type: str) -> Dict[str, Any]:
    system = (
        'You are a careful SEO editor. ' + SEO_FIELDS +
        (' Generate BlogPosting, BreadcrumbList, and evidence-based FAQPage schemas.'
         if page_type == 'blog' else
         ' Never generate BlogPosting. Use schemas appropriate to the supplied page type. '
         'System pages must use noindex,nofollow and no JSON-LD.')
    )
    message = json.dumps({'pageType': page_type, 'page': page}, default=str)[:16000]
    last_error = None
    for model_id in dict.fromkeys(MODEL_CHAIN):
        try:
            response = client().invoke_model(
                modelId=model_id,
                contentType='application/json',
                accept='application/json',
                body=json.dumps(_request(model_id, system, message)).encode('utf-8'),
            )
            parsed = _parse(model_id, json.loads(response['body'].read()))
            return {**parsed, 'model': model_id, 'result': parse_json(parsed['text'])}
        except Exception as error:
            last_error = error
    raise RuntimeError('All configured Bedrock models failed') from last_error
