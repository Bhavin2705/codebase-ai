import hmac
import hashlib
from app.config import settings

def verify_signature(payload_body: bytes, signature_header: str | None) -> bool:
    secret = settings.GITHUB_WEBHOOK_SECRET
    if not secret:
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_digest = hmac.new(
        secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256
    ).hexdigest()
    received_digest = signature_header.split("sha256=")[-1]
    return hmac.compare_digest(expected_digest, received_digest)

