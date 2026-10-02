"""Verified money persists separately from recoverable order finalization.

No blind retries of external effects. Wix adapters retain PENDING markers for
uncertain writes. Initiation and writeback gates remain independent.
"""
import time
from copy import deepcopy

from . import payment_attempt, wix_writeback


def _conditional(error):
    return getattr(error, 'response', {}).get('Error', {}).get('Code') == 'ConditionalCheckFailedException'


def record_paid(attempts, attempt, provider_payment_id):
    """Monotonic, binding-conditional paid state before order-number allocation."""
    now = int(time.time())
    attempts.update_item(Key={'paymentAttemptId': attempt['paymentAttemptId']},
        UpdateExpression='SET #s = :paid, attemptRank = :rank, paidAt = if_not_exists(paidAt, :now), '
                         'updatedAt = :now, verifiedProviderPaymentId = :provider',
        ConditionExpression='attribute_exists(paymentAttemptId) AND referenceId = :ref AND '
                            '(attribute_not_exists(verifiedProviderPaymentId) OR verifiedProviderPaymentId = :provider)',
        ExpressionAttributeNames={'#s': 'status'},
        ExpressionAttributeValues={':paid': payment_attempt.PAYMENT_PAID, ':rank': 100,
            ':now': now, ':provider': provider_payment_id, ':ref': attempt['referenceId']})


def _stage(attempts, attempt_id, stage, **fields):
    names = {'#stage': 'finalizationStage'}
    values = {':stage': stage, ':paid': payment_attempt.PAYMENT_PAID}
    update = ['#stage = :stage']
    for index, (key, value) in enumerate(fields.items()):
        names[f'#f{index}'], values[f':v{index}'] = key, value
        update.append(f'#f{index} = :v{index}')
    attempts.update_item(Key={'paymentAttemptId': attempt_id},
        UpdateExpression='SET ' + ', '.join(update),
        ConditionExpression='#s = :paid',
        ExpressionAttributeNames={**names, '#s': 'status'}, ExpressionAttributeValues=values)


def accept_paid(*, attempts, orders, keys, attempt, outcome):
    """Create the complete internal order and resume only documented writes.

    This never creates a payable invoice. Receipts/notifications have their own
    guarded adapters and must be enabled only after their contracts are attested.
    """
    if not outcome.get('hasOrder') or attempt.get('checkoutMode') != 'WIX_HEADLESS':
        raise ValueError('verified standalone order identity required')
    provider_id = outcome.get('providerPaymentId') or attempt.get('verifiedProviderPaymentId')
    if not provider_id:
        raise ValueError('verified provider payment id required')
    record_paid(attempts, attempt, provider_id)
    snapshot = attempt.get('purchasedSnapshot')
    if not isinstance(snapshot, dict) or not snapshot.get('cart') or not attempt.get('snapshotHash'):
        _stage(attempts, attempt['paymentAttemptId'], 'NEEDS_RECONCILIATION',
               finalizationReason='PURCHASED_SNAPSHOT_MISSING')
        return
    order = {'orderId': outcome['orderId'], 'orderNumber': outcome['orderNumber'],
             'customerId': attempt['customerId'], 'paymentAttemptId': attempt['paymentAttemptId'],
             'referenceId': attempt['referenceId'], 'providerPaymentId': provider_id,
             'amountPaise': attempt['amountPaise'], 'currency': attempt['currency'],
             'purchasedSnapshot': deepcopy(snapshot), 'snapshotHash': attempt['snapshotHash'],
             'checkoutMode': 'WIX_HEADLESS', 'paymentStatus': 'PAYMENT_PAID',
             'finalizationStage': 'INTERNAL_ORDER_CREATED', 'createdAt': int(time.time())}
    try:
        orders.put_item(Item=order, ConditionExpression='attribute_not_exists(orderId)')
    except Exception as error:
        if not _conditional(error):
            raise
        current = orders.get_item(Key={'orderId': outcome['orderId']}, ConsistentRead=True).get('Item') or {}
        if any(current.get(key) != order[key] for key in
               ('customerId', 'paymentAttemptId', 'providerPaymentId', 'snapshotHash', 'orderNumber')):
            raise ValueError('internal order association conflict')
    # A public number may now be returned. Its order record has actually committed.
    _stage(attempts, attempt['paymentAttemptId'], 'INTERNAL_ORDER_CREATED',
           orderId=order['orderId'], orderNumber=order['orderNumber'])
    # Retain paid state even when the site-bound write contract is unavailable.
    # The payload must come from an attested mapping; never guess Wix stock effects.
    if not wix_writeback.is_enabled() or not attempt.get('wixOrderPayload'):
        _stage(attempts, attempt['paymentAttemptId'], 'NEEDS_RECONCILIATION',
               finalizationReason='WIX_WRITE_CONTRACT_REQUIRED')
        return
    from lambda_utils import wix_ecom
    try:
        wix = wix_writeback.create_wix_order(keys, wix_ecom._request,
            order_id=order['orderId'], order_payload=attempt['wixOrderPayload'])
        _stage(attempts, attempt['paymentAttemptId'], 'WIX_ORDER_CREATED', wixOrderId=wix['wixOrderId'])
        wix_writeback.record_external_payment(keys, wix_ecom._request,
            order_id=order['orderId'], wix_order_id=wix['wixOrderId'],
            provider_transaction_id=provider_id, amount_paise=int(attempt['amountPaise']))
        _stage(attempts, attempt['paymentAttemptId'], 'EXTERNAL_PAYMENT_RECORDED')
    except (wix_writeback.WixWritebackPending, wix_writeback.WixWritebackDisabled):
        _stage(attempts, attempt['paymentAttemptId'], 'NEEDS_RECONCILIATION',
               finalizationReason='WIX_READBACK_REQUIRED')
