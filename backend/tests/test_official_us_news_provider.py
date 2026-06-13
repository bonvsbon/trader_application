from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.news import official_us
from app.news.official_us import (
    OfficialCalendarEvent,
    OfficialCalendarSnapshot,
    OfficialUsNewsProvider,
    parse_fomc_calendar,
    parse_nyfed_calendar,
)


NYFED_HTML = """
<td class="ts-data-table-head"><div>June 2026</div></td>
<td width="104" class="somatdR dirColL"><div>10
<span class="ts-accordion-content">
<a href="https://www.bls.gov/">Consumer Price Index</a><br/>(08:30)<br/>
<a href="https://example.com/">Low impact survey</a><br/>(10:00)
</span></div></td>
<td width="104" class="somatdR dirColL"><div>17
<span class="ts-accordion-content">
<a href="https://www.census.gov/">Advance Retail Sales</a><br/>(08:30)
</span></div></td>
"""

FOMC_HTML = """
<h4>2026 FOMC Meetings</h4>
<div class="row fomc-meeting">
  <div class="fomc-meeting__month"><strong>June</strong></div>
  <div class="fomc-meeting__date">16-17*</div>
</div>
<div class="row fomc-meeting">
  <div class="fomc-meeting__month"><strong>July</strong></div>
  <div class="fomc-meeting__date">28-29</div>
</div>
<h4>2025 FOMC Meetings</h4>
<div class="row fomc-meeting">
  <div class="fomc-meeting__month"><strong>December</strong></div>
  <div class="fomc-meeting__date">9-10</div>
</div>
"""


def test_nyfed_parser_keeps_only_high_impact_events_in_eastern_time():
    events = parse_nyfed_calendar(NYFED_HTML)

    assert [event.title for event in events] == [
        "Consumer Price Index",
        "Advance Retail Sales",
    ]
    assert events[0].starts_at == datetime(2026, 6, 10, 12, 30, tzinfo=timezone.utc)
    assert events[0].source == "new_york_fed"


def test_fomc_parser_uses_second_meeting_day_at_2pm_eastern():
    events = parse_fomc_calendar(FOMC_HTML, 2026)

    assert [event.title for event in events] == [
        "FOMC rate decision",
        "FOMC rate decision",
    ]
    assert events[0].starts_at == datetime(2026, 6, 17, 18, 0, tzinfo=timezone.utc)
    assert events[1].starts_at == datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)


def test_official_parsers_reject_unrecognized_pages():
    with pytest.raises(ValueError, match="month heading"):
        parse_nyfed_calendar("<html>maintenance</html>")
    with pytest.raises(ValueError, match="were not found"):
        parse_fomc_calendar("<html>maintenance</html>", 2026)


def test_official_provider_blocks_near_event(make_settings, monkeypatch):
    now = datetime.now(timezone.utc)
    snapshot = OfficialCalendarSnapshot(
        fetched_at=now,
        events=(
            OfficialCalendarEvent(
                title="Consumer Price Index",
                starts_at=now + timedelta(minutes=10),
                source="new_york_fed",
            ),
        ),
    )
    monkeypatch.setattr(
        official_us,
        "fetch_official_us_calendar",
        lambda settings: snapshot,
    )

    risk = OfficialUsNewsProvider(make_settings()).news_risk("XAUUSD")

    assert risk.provider == "official_us"
    assert risk.is_live is True
    assert risk.has_high_impact_within_window is True
    assert "Consumer Price Index" in risk.summary


def test_official_provider_reports_clear_when_no_near_event(
    make_settings,
    monkeypatch,
):
    now = datetime.now(timezone.utc)
    snapshot = OfficialCalendarSnapshot(
        fetched_at=now,
        events=(
            OfficialCalendarEvent(
                title="FOMC rate decision",
                starts_at=now + timedelta(days=3),
                source="federal_reserve",
            ),
        ),
    )
    monkeypatch.setattr(
        official_us,
        "fetch_official_us_calendar",
        lambda settings: snapshot,
    )

    risk = OfficialUsNewsProvider(make_settings()).news_risk("XAUUSD")

    assert risk.is_live is True
    assert risk.has_high_impact_within_window is False
    assert "NY Fed + Federal Reserve" in risk.summary


def test_official_provider_lists_upcoming_events(make_settings, monkeypatch):
    now = datetime.now(timezone.utc)
    snapshot = OfficialCalendarSnapshot(
        fetched_at=now,
        events=(
            OfficialCalendarEvent(
                title="Advance Retail Sales",
                starts_at=now + timedelta(hours=2),
                source="new_york_fed",
            ),
            OfficialCalendarEvent(
                title="FOMC rate decision",
                starts_at=now + timedelta(days=3),
                source="federal_reserve",
            ),
        ),
    )
    monkeypatch.setattr(
        official_us,
        "fetch_official_us_calendar",
        lambda settings: snapshot,
    )

    events = OfficialUsNewsProvider(make_settings()).upcoming_events("XAUUSD")

    assert [event["title"] for event in events] == [
        "Advance Retail Sales",
        "FOMC rate decision",
    ]
    assert events[0]["currency"] == "USD"
    assert events[0]["impact"] == "high"
    assert events[0]["within_block_window"] is False


def test_official_provider_rejects_stale_snapshot(make_settings, monkeypatch):
    snapshot = OfficialCalendarSnapshot(
        fetched_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        events=(),
    )
    monkeypatch.setattr(
        official_us,
        "fetch_official_us_calendar",
        lambda settings: snapshot,
    )

    provider = OfficialUsNewsProvider(make_settings(news_max_age_minutes=15))

    try:
        provider.news_risk("XAUUSD")
    except RuntimeError as exc:
        assert "stale" in str(exc)
    else:
        raise AssertionError("stale official calendar must fail closed")


def test_official_provider_propagates_source_failure(make_settings, monkeypatch):
    def fail_fetch(settings):
        raise RuntimeError("official source unavailable")

    monkeypatch.setattr(official_us, "fetch_official_us_calendar", fail_fetch)

    with pytest.raises(RuntimeError, match="source unavailable"):
        OfficialUsNewsProvider(make_settings()).news_risk("XAUUSD")
