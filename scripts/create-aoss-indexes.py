"""Create OpenSearch Serverless vector indexes for Bedrock Knowledge Bases."""
import json
import boto3
import requests
from requests_aws4auth import AWS4Auth

REGION = 'us-east-1'
AOSS_ENDPOINT = 'https://v3gg4phewwr94mshuda8.us-east-1.aoss.amazonaws.com'

# Get credentials
session = boto3.Session()
credentials = session.get_credentials().get_frozen_credentials()
auth = AWS4Auth(
    credentials.access_key,
    credentials.secret_key,
    REGION,
    'aoss',
    session_token=credentials.token
)

INDEX_BODY = {
    "settings": {
        "index": {
            "knn": True
        }
    },
    "mappings": {
        "properties": {
            "bedrock-knowledge-base-default-vector": {
                "type": "knn_vector",
                "dimension": 1024,
                "method": {
                    "engine": "faiss",
                    "name": "hnsw",
                    "parameters": {}
                }
            },
            "AMAZON_BEDROCK_TEXT_CHUNK": {"type": "text"},
            "AMAZON_BEDROCK_METADATA": {"type": "text"}
        }
    }
}

for index_name in ['bedrock-kb-internal', 'bedrock-kb-external']:
    url = f'{AOSS_ENDPOINT}/{index_name}'
    resp = requests.put(url, auth=auth, json=INDEX_BODY, headers={'Content-Type': 'application/json'})
    print(f'{index_name}: {resp.status_code} - {resp.text}')
