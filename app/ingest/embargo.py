"""엠바고(보도 시점) 감지. 문구를 찾으면 해제 시각을 KST 로 읽어 UTC 로 돌려준다."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from app.settings import KST

KEYWORDS = ["엠바고", "보도 시점", "보도시점", "보도유예", "보도 유예", "이후 보도"]
DATE_RE = re.compile(
    r"(?:(?P<y>\d{4})년\s*)?(?P<m>\d{1,2})월\s*(?P<d>\d{1,2})일(?:\s*\([^)]*\))?"
    r"\s*(?:(?P<ampm>오전|오후|낮|밤|저녁|새벽)\s*)?"
    r"(?:(?P<hh>\d{1,2}):(?P<mm>\d{2})|(?P<h>\d{1,2})시(?:\s*(?P<min>\d{1,2})분)?)?"
)


@dataclass
class Embargo:
    at_utc: str
    quote: str
    time_written: bool


def _to_dt(match: re.Match, default_year: int) -> tuple[datetime, bool]:
    year = int(match["y"]) if match["y"] else default_year
    hour, minute, written = 0, 0, False
    if match["hh"]:
        hour, minute, written = int(match["hh"]), int(match["mm"]), True
    elif match["h"]:
        hour, minute, written = int(match["h"]), int(match["min"] or 0), True
    if match["ampm"] in ("오후", "저녁", "밤") and hour < 12:
        hour += 12
    return datetime(year, int(match["m"]), int(match["d"]), hour, minute, tzinfo=KST), written


def detect_embargo(subject: str, paragraphs: list[str], received_at: str | None) -> Embargo | None:
    default_year = datetime.fromisoformat(received_at).astimezone(KST).year if received_at else datetime.now(KST).year
    candidates = [p for p in paragraphs if any(k in p for k in KEYWORDS)]
    if any(k in subject for k in KEYWORDS):
        candidates.append(subject)          # 본문 문구(연도 포함)를 먼저 본다
    for line in candidates:
        match = DATE_RE.search(line)
        if match:
            dt, written = _to_dt(match, default_year)
            return Embargo(dt.astimezone(timezone.utc).isoformat(), line, written)
    return None


def is_locked(embargo_at: str | None, now_utc: datetime) -> bool:
    return bool(embargo_at) and now_utc < datetime.fromisoformat(embargo_at)
