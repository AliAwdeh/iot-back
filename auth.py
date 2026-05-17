import base64
import hashlib
import hmac
import json
import secrets
import time

from config import JWT_SECRET, JWT_ISSUER, JWT_EXPIRY_SECONDS


def _b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data):
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("utf-8"))


def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    ).hex()

    return f"{salt}${password_hash}"


def verify_password(password, stored_hash):
    try:
        salt, expected_hash = stored_hash.split("$", 1)
        candidate = hash_password(password, salt).split("$", 1)[1]
        return hmac.compare_digest(candidate, expected_hash)
    except Exception:
        return False


def create_jwt(user):
    now = int(time.time())

    header = {
        "alg": "HS256",
        "typ": "JWT",
    }

    payload = {
        "iss": JWT_ISSUER,
        "iat": now,
        "exp": now + JWT_EXPIRY_SECONDS,
        "user_id": user["id"],
        "email": user["email"],
        "role": user["role"],
        "status": user["status"],
    }

    header_part = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_part = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_part}.{payload_part}".encode("utf-8")

    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        signing_input,
        hashlib.sha256,
    ).digest()

    signature_part = _b64url_encode(signature)

    return f"{header_part}.{payload_part}.{signature_part}"


def decode_jwt(token):
    try:
        header_part, payload_part, signature_part = token.split(".")

        signing_input = f"{header_part}.{payload_part}".encode("utf-8")

        expected_signature = hmac.new(
            JWT_SECRET.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()

        actual_signature = _b64url_decode(signature_part)

        if not hmac.compare_digest(expected_signature, actual_signature):
            return None, "Invalid token signature"

        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))

        if payload.get("iss") != JWT_ISSUER:
            return None, "Invalid token issuer"

        if int(time.time()) > int(payload.get("exp", 0)):
            return None, "Token expired"

        return payload, None

    except Exception:
        return None, "Invalid token"
