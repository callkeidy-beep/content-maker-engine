"""개인정보 가리기. AI 로 보내기 전에 쓴다. 원본은 DB 에만 둔다 (docs/journalism-rules.md 5)."""
from __future__ import annotations

import re

PATTERNS = [
    ("[주민번호]", re.compile(r"\b\d{6}-?[1-4]\d{6}\b")),
    ("[전화]", re.compile(r"(?<!\d)0\d{1,2}[-. ]?\d{3,4}[-. ]?\d{4}(?!\d)")),
    ("[이메일]", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("[계좌]", re.compile(r"(?<!\d)\d{3,6}-\d{2,6}-\d{2,8}(?!\d)")),
    ("[주소]", re.compile(
        r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주|[가-힣]{1,4}(?:시|도))"
        r"\s*(?:[가-힣]{1,5}(?:시|군|구)\s*)?[가-힣0-9]{1,10}(?:로|길|동|읍|면)\s*\d+(?:-\d+)?(?:\s*,?\s*\d+호)?")),
]


def mask_text(text: str, names: list[str] | None = None) -> str:
    """정해진 형태를 자리표시자로 바꾼다. 이름은 호출하는 쪽이 넘긴 것만 가린다."""
    out = text
    for label, pattern in PATTERNS:
        out = pattern.sub(label, out)
    for name in sorted({n for n in (names or []) if n and len(n) >= 2}, key=len, reverse=True):
        out = out.replace(name, "[제보자]")
    return out
