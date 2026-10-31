"""Token pricing math."""
from __future__ import annotations

def compute_cost(pricing: dict, provider: str, model: str, usage: dict | None) -> float | None:
    if not usage:
        return None
    rates = (
        pricing.get(provider, {}).get(model)
        or pricing.get(model, {})
        or None
    )
    if not isinstance(rates, dict):
        return None
    try:
        input_tokens = int(usage.get("input_tokens") or 0)
        output_tokens = int(usage.get("output_tokens") or 0)
        cache_read = int(usage.get("cache_read_input_tokens") or usage.get("cache_read") or 0)
        cache_write = int(usage.get("cache_creation_input_tokens") or usage.get("cache_write") or 0)
        uncached = max(input_tokens - cache_read, 0)
        cost = (
            uncached * float(rates.get("input", 0))
            + cache_read * float(rates.get("cache_read", 0))
            + cache_write * float(rates.get("cache_write", 0))
            + output_tokens * float(rates.get("output", 0))
        ) / 1_000_000
        return round(cost, 8)
    except Exception:
        return None


