"""Idempotency key generation."""

from __future__ import annotations

from app.execution.idempotency import make_idempotency_key


def test_deterministic_and_sized():
    a = make_idempotency_key("XAUUSD", "BUY", 0.1)
    b = make_idempotency_key("XAUUSD", "BUY", 0.1)
    assert a == b
    assert len(a) == 32


def test_varies_with_inputs():
    assert make_idempotency_key("XAUUSD", "BUY", 0.1) != make_idempotency_key("XAUUSD", "SELL", 0.1)


def test_bucketed_keys_are_stable_within_window():
    a = make_idempotency_key("XAUUSD", "BUY", 0.1, bucket_seconds=3600)
    b = make_idempotency_key("XAUUSD", "BUY", 0.1, bucket_seconds=3600)
    assert a == b
    assert len(a) == 32
