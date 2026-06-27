"""appsecret_proof helper (Meta Graph API)."""
import hmac
import hashlib


def build_appsecret_proof(access_token: str, app_secret: str) -> str:
    """HMAC-SHA256 of the access token keyed by the app secret (hex). Empty if missing inputs."""
    if not access_token or not app_secret:
        return ''
    return hmac.new(app_secret.encode('utf-8'), access_token.encode('utf-8'), hashlib.sha256).hexdigest()
