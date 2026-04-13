"""QStash signature verification middleware.

Upstash QStash signs every webhook with a JWT in the `Upstash-Signature` header.
We verify it against `QSTASH_CURRENT_SIGNING_KEY` (with `QSTASH_NEXT_SIGNING_KEY`
as a fallback during key rotation periods).

In dev mode (no signing keys configured), we accept an `X-Dev-Worker-Token`
header instead so we can curl the worker endpoints locally via Makefile shortcuts.
The dev token is the same `ENCRYPTION_KEY` from settings — no need for an extra
secret in dev.

Security note: QStash signatures use HS256 with the SHA256 of the request body
in the `body` claim. Replay protection comes from the `iat`/`nbf`/`exp` claims.
"""

import hashlib
import logging
from typing import Annotated

import jwt
from fastapi import Header, HTTPException, Request, status

from app.config import settings

logger = logging.getLogger(__name__)


class WorkerAuthError(HTTPException):
    def __init__(self, detail: str = "Worker authentication failed") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
        )


def _verify_qstash_jwt(token: str, key: str, body_sha256: str) -> dict:
    """Verify a single QStash signature JWT against one signing key."""
    payload = jwt.decode(
        token,
        key,
        algorithms=["HS256"],
        options={"verify_exp": True, "verify_nbf": True, "require": ["iss", "sub", "exp", "body"]},
    )
    if payload.get("body") != body_sha256:
        raise jwt.InvalidTokenError("Body hash mismatch")
    return payload


async def verify_qstash_signature(
    request: Request,
    upstash_signature: Annotated[str | None, Header()] = None,
    x_dev_worker_token: Annotated[str | None, Header()] = None,
) -> None:
    """FastAPI dependency for worker endpoints.

    Accepts EITHER:
    1. A valid `Upstash-Signature` JWT (production)
    2. An `X-Dev-Worker-Token` matching `ENCRYPTION_KEY` (dev only — no signing keys configured)
    """
    keys_configured = bool(
        settings.QSTASH_CURRENT_SIGNING_KEY or settings.QSTASH_NEXT_SIGNING_KEY
    )

    # Dev mode: allow X-Dev-Worker-Token if no signing keys are set
    if not keys_configured:
        if not x_dev_worker_token:
            raise WorkerAuthError(
                "Worker requires X-Dev-Worker-Token in dev mode "
                "(set ENCRYPTION_KEY value as the header)"
            )
        if x_dev_worker_token != settings.ENCRYPTION_KEY:
            raise WorkerAuthError("Invalid X-Dev-Worker-Token")
        return  # dev auth passed

    # Production: verify Upstash-Signature
    if not upstash_signature:
        raise WorkerAuthError("Missing Upstash-Signature header")

    # QStash signs the SHA256 of the body
    body = await request.body()
    body_sha256 = hashlib.sha256(body).hexdigest()

    # Try CURRENT key first, fall back to NEXT (key rotation support)
    last_error: Exception | None = None
    for key_name, key in [
        ("current", settings.QSTASH_CURRENT_SIGNING_KEY),
        ("next", settings.QSTASH_NEXT_SIGNING_KEY),
    ]:
        if not key:
            continue
        try:
            _verify_qstash_jwt(upstash_signature, key, body_sha256)
            logger.debug(f"QStash signature verified with {key_name} key")
            return
        except jwt.InvalidTokenError as e:
            last_error = e
            continue

    raise WorkerAuthError(f"Invalid Upstash-Signature: {last_error}")
