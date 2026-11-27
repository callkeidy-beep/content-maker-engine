"""중복(같은 메일이 두 계정에) 과 수정본(같은 자료의 새 버전) 묶기."""
from __future__ import annotations

import re
from difflib import SequenceMatcher

DUP_SIMILARITY = 0.95        # Message-ID 가 달라도 제목+본문이 이만큼 같으면 중복
VERSION_SIMILARITY = 0.80    # 같은 발신처 + 수정 표시 + 본문 유사도


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def quoted_titles(text: str) -> set[str]:
    return set(re.findall(r"[‘'「『\"]([^’'」』\"]{2,30})[’'」』\"]", text or ""))


def is_duplicate(a: dict, b: dict) -> bool:
    if a.get("message_id") and a.get("message_id") == b.get("message_id"):
        return True
    return (a.get("from_addr") == b.get("from_addr")
            and similarity(a["subject"] + a["body_text"], b["subject"] + b["body_text"]) >= DUP_SIMILARITY)


def is_revision(new: dict, old: dict, marker: bool) -> bool:
    """new 가 old 의 수정본인가. 같은 발신 주소이고, 수정 표시가 있거나 본문이 거의 같아야 한다."""
    if new.get("from_addr") != old.get("from_addr"):
        return False
    sim = similarity(new["body_text"], old["body_text"])
    shared_title = bool(quoted_titles(new["subject"]) & quoted_titles(old["subject"]))
    if marker and (sim >= VERSION_SIMILARITY or shared_title):
        return True
    return sim >= 0.92


def diff_summary(new_paras: list[str], old_paras: list[str]) -> str:
    removed = [p for p in old_paras if p not in new_paras]
    added = [p for p in new_paras if p not in old_paras]
    parts = []
    if removed:
        parts.append("이전: " + removed[0][:60])
    if added:
        parts.append("새: " + added[0][:60])
    return " → ".join(parts) or "본문 변화 없음"
