"""AI module — content brief generation via Claude (or mock).

Same mock-first pattern as DataProviderRouter and OAuth providers: real
Anthropic client when ANTHROPIC_API_KEY is set, deterministic mock when empty.
"""
