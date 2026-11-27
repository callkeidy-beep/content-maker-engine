"""후보 점수 계산 (docs/scoring.md). 1단계는 AI 판정 대신 규칙으로 항목 점수를 매긴다.

인터페이스 score(item, ctx) -> ScoreResult 를 지키면 나중에 AI 판정·회귀 모델로 바꿀 수 있다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.settings import KST

FEATURE_NAMES = {
    "timeliness": "시의성", "impact": "독자 영향력", "exclusivity": "독점성", "fit": "매체 적합도",
    "visual": "시각 자료", "embargo": "엠바고 시점", "follow_up": "후속 취재성", "numbers": "숫자·데이터",
    "duplication": "중복도(감점)",
}
CONSUMER_WORDS = ("티켓", "할인", "관람료", "환불", "지원", "가격", "예매", "무료")
DATE_RE = re.compile(r"(?:(\d{4})년\s*)?(\d{1,2})월\s*(\d{1,2})일")


@dataclass
class ScoreContext:
    now: datetime
    weights: dict
    category_bias: dict
    focus_categories: list
    penalty_per_point: float
    usable_photos: list = field(default_factory=list)   # [(w, h)]
    has_table_attachment: bool = False
    duplicates: int = 0


@dataclass
class ScoreResult:
    total: float
    base: float
    features: dict
    notes: dict


def _parse_korean_amount(text: str) -> float:
    """'1조 2,340억 원' → 원 단위 대략값. 점수용 크기 비교에만 쓴다 (기사에 쓰지 않는다)."""
    total = 0.0
    for num, unit in re.findall(r"(\d[\d,]*(?:\.\d+)?)\s?(조|억|만|천)?", text):
        value = float(num.replace(",", ""))
        total += value * {"조": 1e12, "억": 1e8, "만": 1e4, "천": 1e3}.get(unit, 1)
    return total


def _future_days(texts: list[str], now: datetime, received: datetime) -> int | None:
    now_kst = now.astimezone(KST)
    best = None
    for t in texts:
        for y, m, d in DATE_RE.findall(t):
            year = int(y) if y else received.astimezone(KST).year
            try:
                dt = datetime(year, int(m), int(d), tzinfo=KST)
            except ValueError:
                continue
            if not y and (received.astimezone(KST).date() - dt.date()).days > 60:
                dt = dt.replace(year=year + 1)      # 11월에 받은 자료의 '1월 9일'은 다음 해
            days = (dt.date() - now_kst.date()).days
            if days >= 0 and (best is None or days < best):
                best = days
    return best


def score(item: dict, ctx: ScoreContext) -> ScoreResult:
    f, n = {}, {}
    received = datetime.fromisoformat(item["received_at"])
    facts = [x["text"] for x in item["key_facts"]]

    # 시의성: 수신 뒤 지난 시간 + 본문 속 가장 가까운 앞날
    age_h = (ctx.now - received).total_seconds() / 3600
    recv = 5 if age_h <= 12 else 4 if age_h <= 24 else 3 if age_h <= 48 else 2 if age_h <= 96 else 1
    days = _future_days(facts, ctx.now, received)
    if days is None:
        f["timeliness"], n["timeliness"] = float(recv), f"수신 {age_h:.0f}시간 전"
    else:
        ev = 5 if days <= 7 else 4 if days <= 21 else 3 if days <= 45 else 2
        f["timeliness"] = round((recv + ev) / 2, 1)
        n["timeliness"] = f"수신 {age_h:.0f}시간 전, {days}일 뒤 일정"

    # 독자 영향력: 돈·사람 규모, 생활과의 연결
    nums = [x["value"] for x in item["entities"].get("numbers", [])]
    impact, why = 1, []
    money = max([_parse_korean_amount(v) for v in nums if v.endswith("원")] or [0])
    if money >= 1e9:
        impact += 2; why.append("10억 원 이상 금액")
    elif money >= 1e8:
        impact += 1; why.append("억 원 단위 금액")
    people = max([_parse_korean_amount(v) for v in nums if v.endswith("명")] or [0])
    if people >= 10000:
        impact += 1; why.append("만 명 이상 규모")
    if any(w in " ".join(facts) for w in CONSUMER_WORDS):
        impact += 1; why.append("독자 생활(값·지원·환불)과 연결")
    f["impact"], n["impact"] = float(min(impact, 5)), ", ".join(why) or "규모 신호 없음"

    # 독점성
    if item["kind"] == "tip":
        f["exclusivity"], n["exclusivity"] = 3.0, "제보(+1)"
    elif item["mass_distribution"]:
        f["exclusivity"], n["exclusivity"] = 1.0, "일괄 배포 흔적"
    else:
        f["exclusivity"], n["exclusivity"] = 2.0, "보도자료"

    # 매체 적합도
    cat = item["category"]
    if cat in ctx.focus_categories:
        f["fit"], n["fit"] = 5.0, "기본 매체 중점 분야"
    elif cat == "other":
        f["fit"], n["fit"] = 1.0, "기타 분야"
    else:
        f["fit"], n["fit"] = 2.0, "중점 분야 밖"

    # 시각 자료
    photos = ctx.usable_photos
    if not photos:
        v = 0
    elif len(photos) == 1:
        v = 2
    elif len(photos) == 2:
        v = 3
    else:
        v = 5 if all((w or 0) >= 1080 for w, _ in photos) else 4
    f["visual"], n["visual"] = float(v), f"사용 가능 사진 {len(photos)}장"

    # 엠바고 시점
    emb = item.get("embargo_at")
    if not emb:
        f["embargo"], n["embargo"] = 3.0, "엠바고 없음(가정: 3점)"
    else:
        at = datetime.fromisoformat(emb)
        when = at.astimezone(KST).strftime("%m/%d %H:%M")
        if at <= ctx.now:
            f["embargo"], n["embargo"] = 3.0, f"이미 해제({when})"
        elif at.astimezone(KST).date() == ctx.now.astimezone(KST).date():
            f["embargo"], n["embargo"] = 5.0, f"오늘 해제({when})"
        else:
            f["embargo"], n["embargo"] = 1.0, f"내일 이후 해제({when})"

    # 후속 취재성
    sig = {s["term"] for s in item.get("signals", [])}
    fu = 1 + len(sig) + (2 if item["kind"] == "tip" else 0) + int(item.get("follow_boost") or 0)
    f["follow_up"] = float(min(fu, 5))
    n["follow_up"] = ("제보 " if item["kind"] == "tip" else "") + (f"확인할 표현 {len(sig)}개" if sig else "확인할 표현 없음")

    # 숫자·데이터
    c = len(nums)
    s = 0 if c == 0 else 1 if c == 1 else 2 if c == 2 else 3 if c <= 4 else 4 if c <= 6 else 5
    note = f"숫자 {c}개"
    if ctx.has_table_attachment:
        s = max(s, 4); note += ", 엑셀 표 첨부"
    f["numbers"], n["numbers"] = float(s), note

    # 중복도(감점)
    f["duplication"] = float(min(ctx.duplicates, 5))
    n["duplication"] = f"최근 비슷한 자료 {ctx.duplicates}건"

    weights = ctx.weights
    base = sum(weights.get(k, 0) * f[k] for k in weights) / 5 * 100
    total = base + ctx.category_bias.get(cat, 0) - f["duplication"] * ctx.penalty_per_point
    total = max(0.0, min(100.0, total))
    return ScoreResult(round(total, 1), round(base, 1), f, n)


def top_feature(features: dict, weights: dict) -> str:
    """가중치를 곱한 기여가 가장 큰 항목."""
    keys = [k for k in features if k != "duplication"]
    return max(keys, key=lambda k: (features[k] * weights.get(k, 0), features[k]))

