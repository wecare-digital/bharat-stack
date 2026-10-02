"""Remember WhatsApp login with an opaque HttpOnly cookie and encrypted server refresh custody.

The browser keeps only its existing short-lived access token. It never persists a refresh token.
Every response is no-store; secrets, OTPs and token-bearing request bodies are never logged.
"""
import base64
import json
import os
import time

import boto3
from botocore.exceptions import ClientError
from lambda_utils import customer_auth, customer_session as sessions
from lambda_utils.customer_session_store import SessionStore
from lambda_utils.response import cors_response, extract_origin

CLIENT_ID = '4avmt9n4gpmkvkdk88qbtit33o'
ORIGIN = 'https://wecare.digital'


def handler(event, context):
    origin = extract_origin(event)
    def response(code, data):
        result = cors_response(code, data, origin)
        # Both headers, via the shared helper, not a hand-set Cache-Control. This response can
        # carry a csrfToken, and it is served through the Amplify `/api/<*>` status-200 rewrite,
        # so a shared cache handing one customer's token to another is the risk being closed.
        # `harden_session_headers` is also what tests/test_session_response_is_not_cacheable.py
        # requires every csrfToken-bearing handler to use, so the pair cannot drift apart here.
        result['headers'] = sessions.harden_session_headers(result['headers'])
        return result
    if origin != ORIGIN:
        return response(403, {'error': 'ORIGIN_REQUIRED'})
    store = SessionStore(boto3.resource('dynamodb').Table(os.environ['CUSTOMER_SESSIONS_TABLE']))
    kms = boto3.client('kms')
    cognito = boto3.client('cognito-idp')
    key_id = os.environ['CUSTOMER_SESSION_KMS_KEY_ID']
    encryption_context = {'purpose': 'wecare-customer-refresh', 'clientId': CLIENT_ID}

    def seal(token):
        return base64.b64encode(kms.encrypt(KeyId=key_id, Plaintext=token.encode(),
                              EncryptionContext=encryption_context)['CiphertextBlob']).decode()

    try:
        rotation = cognito.describe_user_pool_client(UserPoolId='us-east-1_46ULYuukt',
                     ClientId=CLIENT_ID)['UserPoolClient'].get('RefreshTokenRotation', {}).get('Feature') == 'ENABLED'
    except Exception:
        return response(503, {'error': 'TEMPORARILY_UNAVAILABLE'})

    def provider_refresh(token):
        try:
            if rotation:
                return cognito.get_tokens_from_refresh_token(ClientId=CLIENT_ID,
                        RefreshToken=token)['AuthenticationResult']
            return cognito.initiate_auth(ClientId=CLIENT_ID, AuthFlow='REFRESH_TOKEN_AUTH',
                        AuthParameters={'REFRESH_TOKEN': token})['AuthenticationResult']
        except ClientError as error:
            if error.response['Error']['Code'] in ('NotAuthorizedException', 'UserNotFoundException'):
                raise sessions.RefreshFailed('verification required') from None
            raise sessions.RefreshUnavailable('temporarily unavailable') from None

    def refresh(ref, stored_rotation):
        token = kms.decrypt(KeyId=key_id, CiphertextBlob=base64.b64decode(ref),
                            EncryptionContext=encryption_context)['Plaintext'].decode()
        result = provider_refresh(token)
        return {'accessToken': result['AccessToken'], 'expiresIn': result['ExpiresIn'], 'refreshRef': seal(result['RefreshToken']) if result.get('RefreshToken') else ref}

    try:
        body = json.loads(event.get('body') or '{}')
        action = body.get('action')
        cookie = sessions.read_cookie({**(event.get('headers') or {}),
                    'cookie': '; '.join(event.get('cookies') or []) or (event.get('headers') or {}).get('cookie', '')})
        headers = {str(k).lower(): v for k, v in (event.get('headers') or {}).items()}
        if action == 'exchange':
            identity = customer_auth.authenticate(event)
            token = str(body.get('refreshToken') or '')
            if not token or len(token) > 4096:
                raise sessions.SessionInvalid('refresh custody required')
            # Prove the refresh token belongs to the same customer as the access token.
            #
            # BOTH COMPARISONS CURRENTLY TEST THE SAME VALUE, AND THAT IS KNOWN. Since
            # 2026-10-02 `customer_auth.customer_id_from_attributes` derives `customer_id`
            # from the Cognito `sub`, which is also what `subject` carries, so this reads as
            # two independent checks and is one. It is still correct and still rejects a
            # mismatched refresh owner - one sufficient check, not a vacuous one.
            #
            # DO NOT "TIDY" THE SECOND COMPARISON AWAY. Keeping both costs nothing and makes
            # the check strengthen by itself the day `customer_id` gains an independent
            # source - which is a live possibility, because the alternative to `sub` was a
            # `custom:customer_id` attribute that could still be added and backfilled later
            # (see `customer_id_from_attributes` for why that is owner work and why a
            # fallback was refused). Deleting it now would quietly remove that future
            # protection, and nothing here would fail to tell you.
            renewed = provider_refresh(token)
            proven = customer_auth.authenticate({'headers': {'authorization': 'Bearer ' + renewed['AccessToken']}})
            if proven.customer_id != identity.customer_id or proven.subject != identity.subject:
                raise sessions.SessionInvalid('refresh owner mismatch')
            persistent = body.get('persistent') is not False
            opaque, view = sessions.create_session(store, customer_id=identity.customer_id,
                         refresh_ref=seal(renewed.get('RefreshToken') or token), persistent=persistent, rotation_enabled=rotation)
            if cookie:
                sessions.revoke(store, cookie)
            result = response(200, {'csrfToken': view.csrf_token, 'expiresAt': view.absolute_expires_at * 1000,
                                    'persistent': persistent})
            result['cookies'] = [sessions.build_set_cookie(opaque, persistent=persistent, absolute_expires_at=view.absolute_expires_at)]
        elif action in ('refresh', 'logout'):
            view = sessions.validate(store, cookie)
            sessions.assert_csrf(view, str(headers.get('x-customer-csrf') or ''))
            if action == 'logout':
                sessions.revoke(store, cookie)
                result = response(200, {'signedOut': True})
                result['cookies'] = [sessions.build_clear_cookie()]
            else:
                renewed = sessions.refresh_access_token(store, cookie, cognito_refresh=refresh)
                result = response(200, {'accessToken': renewed['accessToken'],
                    'expiresAt': (int(time.time()) + renewed['expiresIn']) * 1000})
        else:
            result = response(400, {'error': 'UNKNOWN_ACTION'})
    except (sessions.SessionInvalid, sessions.RefreshFailed, customer_auth.CustomerNotAuthenticated):
        result = response(401, {'error': 'VERIFICATION_REQUIRED'})
        result['cookies'] = [sessions.build_clear_cookie()]
    except sessions.CsrfInvalid:
        result = response(403, {'error': 'CSRF_REQUIRED'})
    except Exception:
        result = response(503, {'error': 'TEMPORARILY_UNAVAILABLE'})
    result['headers'] = sessions.harden_session_headers(result['headers'])
    return result
