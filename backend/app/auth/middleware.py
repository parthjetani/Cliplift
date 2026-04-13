"""Supabase JWT validation.

Supabase has TWO JWT signing modes:

1. **Asymmetric (ES256/RS256)** — newer, default for new projects.
   Tokens carry a `kid` header pointing to a public key fetched from
   `{SUPABASE_URL}/auth/v1/.well-known/jwks.json`. Supports key rotation.

2. **Symmetric (HS256)** — legacy, used by older projects.
   Tokens are signed with a shared secret (`SUPABASE_JWT_SECRET`).

This module supports both: it inspects the token header's `alg` field and
picks the correct verification path. JWKS responses are cached for 1 hour.
"""

import logging

import jwt
from fastapi import HTTPException, status
from jwt import PyJWKClient

from app.auth.schemas import SupabaseUser
from app.config import settings

logger = logging.getLogger(__name__)


class JWTValidationError(HTTPException):
    """Raised when a JWT is missing, expired, or malformed."""

    def __init__(self, detail: str = "Invalid or expired token") -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


# JWKS client — caches public keys for 1 hour, refetches on cache miss
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Lazy singleton for the JWKS client (built on first use)."""
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True, lifespan=3600)
    return _jwks_client


def decode_supabase_jwt(token: str) -> SupabaseUser:
    """Verify a Supabase JWT (HS256 or ES256/RS256) and return the user.

    Args:
        token: Raw JWT (without the "Bearer " prefix)

    Returns:
        SupabaseUser with id, email, role

    Raises:
        JWTValidationError: If the token is invalid, expired, or malformed
    """
    # Inspect header to pick verification strategy
    try:
        header = jwt.get_unverified_header(token)
    except jwt.DecodeError as e:
        raise JWTValidationError(f"Malformed token header: {e}") from e

    alg = header.get("alg", "")
    common_options = {
        "verify_exp": True,
        "require": ["sub", "email", "exp"],
    }

    try:
        if alg == "HS256":
            # Symmetric — uses shared secret from .env
            if not settings.SUPABASE_JWT_SECRET:
                logger.error("SUPABASE_JWT_SECRET is not set — HS256 verification will fail")
                raise JWTValidationError("Server auth misconfigured")
            payload = jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                audience="authenticated",
                options=common_options,
            )
        elif alg in ("ES256", "RS256"):
            # Asymmetric — fetch public key from Supabase JWKS endpoint
            try:
                signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
            except jwt.PyJWKClientError as e:
                logger.warning(f"JWKS lookup failed: {e}")
                raise JWTValidationError(f"Cannot resolve signing key: {e}") from e

            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[alg],
                audience="authenticated",
                options=common_options,
            )
        else:
            raise JWTValidationError(f"Unsupported JWT algorithm: {alg}")

    except jwt.ExpiredSignatureError as e:
        raise JWTValidationError("Token has expired") from e
    except jwt.InvalidAudienceError as e:
        raise JWTValidationError("Invalid token audience") from e
    except jwt.InvalidTokenError as e:
        logger.debug(f"JWT decode failed: {e}")
        raise JWTValidationError(f"Invalid token: {e}") from e

    try:
        return SupabaseUser(
            id=payload["sub"],
            email=payload["email"],
            role=payload.get("role", "authenticated"),
            aud=payload.get("aud", "authenticated"),
        )
    except (KeyError, ValueError) as e:
        raise JWTValidationError(f"Malformed token payload: {e}") from e


def extract_bearer_token(authorization_header: str | None) -> str:
    """Pull the JWT out of an `Authorization: Bearer <token>` header."""
    if not authorization_header:
        raise JWTValidationError("Missing Authorization header")

    parts = authorization_header.split(maxsplit=1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise JWTValidationError("Authorization header must be 'Bearer <token>'")

    return parts[1]
