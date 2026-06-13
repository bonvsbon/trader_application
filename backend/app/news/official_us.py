"""Free official-US economic calendar for USD risk windows."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import httpx

from app.core.config import Settings
from app.domain.models import NewsRisk

NYFED_CALENDAR_URL = "https://www.newyorkfed.org/research/calendars/nationalecon_cal"
FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
EASTERN = ZoneInfo("America/New_York")

HIGH_IMPACT_TITLES = (
    "employment situation",
    "consumer price index",
    "producer price index",
    "jolts",
    "adp national employment report",
    "ism manufacturing",
    "ism non-manufacturing",
    "initial claims",
    "advance retail sales",
    "advance durable goods",
    "gross domestic product",
    "personal income and the pce deflator",
    "personal income and outlays",
)


@dataclass(frozen=True)
class OfficialCalendarEvent:
    title: str
    starts_at: datetime
    source: str


@dataclass(frozen=True)
class OfficialCalendarSnapshot:
    fetched_at: datetime
    events: tuple[OfficialCalendarEvent, ...]


class _NyFedCalendarParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.month_year: str | None = None
        self.events: list[tuple[int, str, str]] = []
        self._heading_depth = 0
        self._heading_parts: list[str] = []
        self._cell_depth = 0
        self._cell_parts: list[str] = []
        self._cell_titles: list[str] = []
        self._anchor_depth = 0
        self._anchor_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        if tag == "td" and "ts-data-table-head" in classes:
            self._heading_depth = 1
            self._heading_parts = []
            return
        if self._heading_depth:
            self._heading_depth += 1
        if tag == "td" and "somatdR" in classes and attributes.get("width") == "104":
            self._cell_depth = 1
            self._cell_parts = []
            self._cell_titles = []
            return
        if self._cell_depth:
            self._cell_depth += 1
            if tag == "a":
                self._anchor_depth = 1
                self._anchor_parts = []
        elif self._anchor_depth:
            self._anchor_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._anchor_depth:
            self._anchor_depth -= 1
            if self._anchor_depth == 0:
                title = " ".join("".join(self._anchor_parts).split())
                if title:
                    self._cell_titles.append(title)
            if self._cell_depth:
                self._cell_depth -= 1
            return
        if self._heading_depth:
            self._heading_depth -= 1
            if self._heading_depth == 0:
                heading = " ".join("".join(self._heading_parts).split())
                if re.fullmatch(r"[A-Za-z]+ \d{4}", heading):
                    self.month_year = heading
            return
        if self._cell_depth:
            self._cell_depth -= 1
            if self._cell_depth == 0:
                text = " ".join(" ".join(self._cell_parts).split())
                day_match = re.match(r"(\d{1,2})\b", text)
                times = re.findall(r"\((\d{2}:\d{2})\)", text)
                if day_match:
                    day = int(day_match.group(1))
                    self.events.extend(
                        (day, title, event_time)
                        for title, event_time in zip(
                            self._cell_titles,
                            times,
                            strict=False,
                        )
                    )

    def handle_data(self, data: str) -> None:
        if self._anchor_depth:
            self._anchor_parts.append(data)
        if self._heading_depth:
            self._heading_parts.append(data)
        if self._cell_depth:
            self._cell_parts.append(data)


class _FomcCalendarParser(HTMLParser):
    def __init__(self, year: int) -> None:
        super().__init__(convert_charrefs=True)
        self.year = year
        self.meetings: list[tuple[str, str]] = []
        self._active_year = False
        self._row_depth = 0
        self._field_depth = 0
        self._field: str | None = None
        self._month_parts: list[str] = []
        self._date_parts: list[str] = []
        self._all_text: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        classes = set(dict(attrs).get("class", "").split())
        if tag == "div" and "fomc-meeting" in classes:
            self._row_depth = 1
            self._month_parts = []
            self._date_parts = []
            return
        if self._row_depth and tag == "div":
            self._row_depth += 1
            if "fomc-meeting__month" in classes:
                self._field = "month"
                self._field_depth = 1
            elif "fomc-meeting__date" in classes:
                self._field = "date"
                self._field_depth = 1
        elif self._field_depth and tag == "div":
            self._field_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag != "div":
            return
        if self._field_depth:
            self._field_depth -= 1
            if self._field_depth == 0:
                self._field = None
        if self._row_depth:
            self._row_depth -= 1
            if self._row_depth == 0 and self._active_year:
                month = " ".join("".join(self._month_parts).split())
                dates = " ".join("".join(self._date_parts).split())
                if month and dates:
                    self.meetings.append((month, dates))

    def handle_data(self, data: str) -> None:
        self._all_text.append(data)
        normalized = " ".join(data.split())
        match = re.fullmatch(r"(\d{4}) FOMC Meetings", normalized)
        if match:
            self._active_year = int(match.group(1)) == self.year
        if self._field == "month":
            self._month_parts.append(data)
        elif self._field == "date":
            self._date_parts.append(data)


def parse_nyfed_calendar(html: str) -> list[OfficialCalendarEvent]:
    parser = _NyFedCalendarParser()
    parser.feed(html)
    if parser.month_year is None:
        raise ValueError("New York Fed calendar month heading was not found")
    month_start = datetime.strptime(parser.month_year, "%B %Y")
    events: list[OfficialCalendarEvent] = []
    for day, title, event_time in parser.events:
        if not any(token in title.casefold() for token in HIGH_IMPACT_TITLES):
            continue
        hour, minute = (int(part) for part in event_time.split(":"))
        starts_at = datetime(
            month_start.year,
            month_start.month,
            day,
            hour,
            minute,
            tzinfo=EASTERN,
        ).astimezone(timezone.utc)
        events.append(
            OfficialCalendarEvent(
                title=title,
                starts_at=starts_at,
                source="new_york_fed",
            )
        )
    return events


def parse_fomc_calendar(html: str, year: int) -> list[OfficialCalendarEvent]:
    parser = _FomcCalendarParser(year)
    parser.feed(html)
    if not parser.meetings:
        raise ValueError(f"Federal Reserve FOMC meetings for {year} were not found")
    events: list[OfficialCalendarEvent] = []
    for month_name, date_range in parser.meetings:
        day_numbers = [int(value) for value in re.findall(r"\d{1,2}", date_range)]
        if not day_numbers:
            continue
        decision_day = day_numbers[-1]
        month = datetime.strptime(month_name, "%B").month
        starts_at = datetime(
            year,
            month,
            decision_day,
            14,
            0,
            tzinfo=EASTERN,
        ).astimezone(timezone.utc)
        events.append(
            OfficialCalendarEvent(
                title="FOMC rate decision",
                starts_at=starts_at,
                source="federal_reserve",
            )
        )
    return events


_cache_lock = threading.Lock()
_cached_snapshot: OfficialCalendarSnapshot | None = None
_cached_until = 0.0


def clear_official_us_cache() -> None:
    global _cached_snapshot, _cached_until
    with _cache_lock:
        _cached_snapshot = None
        _cached_until = 0.0


def fetch_official_us_calendar(settings: Settings) -> OfficialCalendarSnapshot:
    global _cached_snapshot, _cached_until
    now_monotonic = time.monotonic()
    with _cache_lock:
        if _cached_snapshot is not None and now_monotonic < _cached_until:
            return _cached_snapshot

    timeout = httpx.Timeout(settings.news_official_timeout_sec)
    headers = {"User-Agent": "ThangRod/0.1 economic-calendar safety monitor"}
    with httpx.Client(timeout=timeout, follow_redirects=False, headers=headers) as client:
        nyfed_response = client.get(NYFED_CALENDAR_URL)
        nyfed_response.raise_for_status()
        fomc_response = client.get(FOMC_CALENDAR_URL)
        fomc_response.raise_for_status()

    fetched_at = datetime.now(timezone.utc)
    events = [
        *parse_nyfed_calendar(nyfed_response.text),
        *parse_fomc_calendar(fomc_response.text, fetched_at.year),
    ]
    snapshot = OfficialCalendarSnapshot(
        fetched_at=fetched_at,
        events=tuple(sorted(events, key=lambda event: event.starts_at)),
    )
    with _cache_lock:
        _cached_snapshot = snapshot
        _cached_until = time.monotonic() + settings.news_official_cache_minutes * 60
    return snapshot


class OfficialUsNewsProvider:
    name = "official_us"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.block_window_minutes = settings.risk_news_block_window_min
        self.max_age_minutes = settings.news_max_age_minutes

    def news_risk(self, symbol: str) -> NewsRisk:
        if not symbol.upper().startswith(("XAU", "XAG", "USD")):
            return NewsRisk(
                summary=f"Official US calendar does not cover {symbol.upper()}",
                provider=self.name,
                is_live=False,
            )
        snapshot = fetch_official_us_calendar(self.settings)
        now = datetime.now(timezone.utc)
        age_minutes = (now - snapshot.fetched_at).total_seconds() / 60.0
        if age_minutes > self.max_age_minutes:
            raise RuntimeError(
                f"Official US economic calendar is stale ({age_minutes:.0f} min old)"
            )
        nearby = [
            event
            for event in snapshot.events
            if abs((event.starts_at - now).total_seconds() / 60.0)
            <= self.block_window_minutes
        ]
        if not nearby:
            return NewsRisk(
                has_high_impact_within_window=False,
                score=0.0,
                summary=(
                    "Official US calendar clear; "
                    f"NY Fed + Federal Reserve fetched {age_minutes:.1f} min ago"
                ),
                provider=self.name,
                is_live=True,
            )
        nearest = min(
            nearby,
            key=lambda event: abs((event.starts_at - now).total_seconds()),
        )
        minutes = (nearest.starts_at - now).total_seconds() / 60.0
        return NewsRisk(
            has_high_impact_within_window=True,
            minutes_to_next_high_impact=minutes,
            score=1.0,
            summary=f"USD high impact: {nearest.title} ({nearest.source})",
            provider=self.name,
            is_live=True,
        )

    def upcoming_events(self, symbol: str, limit: int = 8) -> list[dict]:
        if not symbol.upper().startswith(("XAU", "XAG", "USD")):
            return []
        snapshot = fetch_official_us_calendar(self.settings)
        now = datetime.now(timezone.utc)
        earliest = now - timedelta(minutes=self.block_window_minutes)
        events = [
            event
            for event in snapshot.events
            if event.starts_at >= earliest
        ]
        return [
            {
                "title": event.title,
                "currency": "USD",
                "impact": "high",
                "starts_at": event.starts_at.isoformat(),
                "minutes_until": round(
                    (event.starts_at - now).total_seconds() / 60.0,
                    1,
                ),
                "within_block_window": (
                    abs((event.starts_at - now).total_seconds() / 60.0)
                    <= self.block_window_minutes
                ),
                "source": event.source,
            }
            for event in events[: max(1, min(limit, 20))]
        ]
