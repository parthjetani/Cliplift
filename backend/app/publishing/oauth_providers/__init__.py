"""OAuth provider implementations.

Each provider implements the `OAuthProvider` interface from `base.py`. The
factory in `oauth_factory.py` picks the real provider when client_id/secret
env vars are set, otherwise falls back to `MockOAuthProvider` for dev/testing.
"""
