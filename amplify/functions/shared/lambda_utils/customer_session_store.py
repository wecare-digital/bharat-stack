"""DynamoDB adapter for customer_session; encrypted refresh custody stays server-side.

refreshRef is a KMS ciphertext capsule, not a plaintext token or a browser value.
The pure session policy remains responsible for idle/absolute expiry and refresh leases.
"""
from botocore.exceptions import ClientError


class SessionStore:
    def __init__(self, table):
        self.table = table

    def put_session(self, row):
        self.table.put_item(Item=row, ConditionExpression='attribute_not_exists(sidHash)')

    def get_session(self, key):
        return self.table.get_item(Key={'sidHash': key}, ConsistentRead=True).get('Item')

    def delete_session(self, key):
        self.table.delete_item(Key={'sidHash': key})

    def _update(self, key, expression, values, condition='attribute_exists(sidHash)'):
        return self.table.update_item(Key={'sidHash': key}, UpdateExpression=expression,
                                      ConditionExpression=condition, ExpressionAttributeValues=values)

    def touch_session(self, key, *, last_seen_at, idle_expires_at):
        self._update(key, 'SET lastSeenAt = :seen, idleExpiresAt = :idle',
                     {':seen': last_seen_at, ':idle': idle_expires_at},
                     'attribute_exists(sidHash) AND attribute_not_exists(revokedAt)')

    def revoke_session(self, key, *, revoked_at):
        self._update(key, 'SET revokedAt = :now REMOVE refreshRef', {':now': revoked_at})

    def claim_refresh(self, key, *, now, lease_seconds):
        try:
            self._update(key, 'SET refreshInFlight = :now', {':now': now, ':cutoff': now - lease_seconds},
                         'attribute_exists(sidHash) AND attribute_not_exists(revokedAt) AND refreshInFlight <= :cutoff')
            return True
        except ClientError as error:
            if error.response['Error']['Code'] == 'ConditionalCheckFailedException':
                return False
            raise

    def record_refresh(self, key, *, refresh_ref, last_seen_at, idle_expires_at):
        self._update(key, 'SET refreshRef = :ref, lastSeenAt = :seen, idleExpiresAt = :idle',
                     {':ref': refresh_ref, ':seen': last_seen_at, ':idle': idle_expires_at},
                     'attribute_exists(sidHash) AND attribute_not_exists(revokedAt)')

    def release_refresh(self, key):
        self._update(key, 'SET refreshInFlight = :zero', {':zero': 0})
