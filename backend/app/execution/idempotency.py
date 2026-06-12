"""Idempotency helpers.

The durable guarantee is the UNIQUE constraint on `orders.idempotency_key`:
re-submitting the same key returns the prior result instead of placing a new
order. For auto-generated requests, `make_idempotency_key` derives a stable key
from the order's defining fields (optionally bucketed by time).
"""

from __future__ import annotations

import hashlib
import time

from app.domain.models import OrderRequest

# How recently a near-identical order (different key) counts as a suspected
# accidental duplicate. Operational guard, not a risk parameter.
DUPLICATE_WINDOW_SECONDS = 5


def make_idempotency_key(*parts: object, bucket_seconds: int | None = None) -> str:
    """Deterministic 32-char key from the given parts.

    Pass `bucket_seconds` to make otherwise-identical requests dedupe only within
    a time window (e.g. one auto signal per interval).
    """
    raw = "|".join(str(p) for p in parts)
    if bucket_seconds:
        raw += f"|{int(time.time() // bucket_seconds)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def make_duplicate_fingerprint(
    request: OrderRequest,
    *,
    bucket_seconds: int = DUPLICATE_WINDOW_SECONDS,
) -> str:
    """Stable fingerprint for concurrent near-identical submissions."""
    return make_idempotency_key(
        "duplicate",
        request.symbol.upper(),
        request.side.value,
        request.volume,
        request.sl,
        request.tp,
        bucket_seconds=bucket_seconds,
    )
