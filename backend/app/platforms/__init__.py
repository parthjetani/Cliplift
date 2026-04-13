"""Platform adapters — DataProviderRouter + per-platform implementations.

All adapters fall back to mock data when their API key is missing, so the full
stack can run end-to-end without paying for any external service.
"""
