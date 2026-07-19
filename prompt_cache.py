# prompt_cache.py
"""Utilities for prompt caching to reduce token costs on repeated
static system prompt prefixes."""

from providers import resolve_role, _headers

def supports_prompt_caching(role: str) -> bool:
    """Check if the provider for a role supports prompt caching."""
    try:
        prov, model, _ = resolve_role(role)
        return prov["kind"] == "anthropic"
    except Exception:
        return False

def add_cache_breakpoint(system_prompt: str, role: str) -> dict:
    """Add prompt caching markers for providers that support them.

    For Anthropic: insert cache_control on the system block.
    For OpenAI: uses automatic prefix caching (no explicit markers needed,
    but long matching prefixes benefit from keeping them stable).

    Returns a dict with 'system' and 'extra_body' to merge into the
    chat_complete call.
    """
    prov_kind = ""
    try:
        prov, _, _ = resolve_role(role)
        prov_kind = prov["kind"]
    except Exception:
        pass

    if prov_kind == "anthropic":
        # Anthropic prompt caching: mark the system block for caching
        # The cache lasts 5 minutes; hits are 90% cheaper
        return {
            "system": system_prompt,
            "extra_body": {
                "system": [
                    {
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
        }

    # OpenAI and compatible: automatic prefix caching, no markers needed.
    # Just ensure the system prompt is stable (it is — it comes from
    # get_prompt which is deterministic per preset).
    return {"system": system_prompt, "extra_body": {}}

# Static prompt segments that should be cached across calls.
# These are the large constant blocks embedded in system prompts.
CACHEABLE_SEGMENTS = [
    # From prompts.py — these are the long constant strings
    "Lore categories:",
    "Lorebook types:",
    "PLAYER SPEECH AUTHORITY",
    "You are the DIRECTOR",
    "You are the PERCEPTION layer",
    "You are the NARRATOR",
    "You are the MAPPING agent",
]

def estimate_cacheable_tokens(system_prompt: str) -> int:
    """Rough estimate of how many tokens in the system prompt are
    from stable, cacheable segments."""
    cacheable_chars = 0
    for segment in CACHEABLE_SEGMENTS:
        idx = system_prompt.find(segment)
        if idx >= 0:
            # Estimate the segment extends to the next section break
            # (double newline after a substantial block)
            end = system_prompt.find("\n\n", idx + 100)
            if end > idx:
                cacheable_chars += end - idx
    # Rough: ~4 chars per token
    return cacheable_chars // 4