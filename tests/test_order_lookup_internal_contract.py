"""Order lookup must use IAM invocation context, never a browser Origin."""
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]


def test_flow_lookup_without_origin_accepts_internal_context_and_rejects_gateway():
    path = ROOT / 'amplify/functions/messaging/whatsapp-business-api/flows/orders.py'
    spec = importlib.util.spec_from_file_location('order_lookup_contract', path)
    orders = importlib.util.module_from_spec(spec)
    with patch('boto3.client'), patch('boto3.resource'):
        spec.loader.exec_module(orders)
    orders.dynamodb.Table.return_value.query.return_value = {'Items': []}
    orders.lambda_client = MagicMock()
    orders.lambda_client.invoke.return_value = {
        'Payload': io.BytesIO(json.dumps({'body': json.dumps({'orders': []})}).encode())
    }
    assert orders.fetch_orders_for_flow('', 'customer@example.test') == []
    event = json.loads(orders.lambda_client.invoke.call_args.kwargs['Payload'])
    assert event['rawPath'] == '/wix-store/orders'
    assert event['queryStringParameters']['email'] == 'customer@example.test'
    assert 'origin' not in event.get('headers', {})

    from lambda_utils.middleware import require_auth
    with patch('lambda_utils.middleware.cognito') as cognito:
        assert require_auth(event) is None
        cognito.get_user.assert_not_called()
        event['requestContext']['apiId'] = 'gateway-test'
        response = require_auth(event)
        assert response['statusCode'] == 401
        cognito.get_user.assert_not_called()
