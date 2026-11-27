"""편집자 평가 저장. 평가는 '승인'이 아니다. 승인은 따로 누른다."""
from __future__ import annotations

import sqlite3
from datetime import datetime

from app.db import set_status, utcnow
from app.ingest.embargo import is_locked

TAGS = {"adopt": "채택", "hold": "보류", "drop": "폐기", "follow": "후속취재"}
TAG_STATUS = {"adopt": "평가됨", "hold": "보류", "drop": "폐기", "follow": "후속취재", None: "평가됨"}


class RatingError(ValueError):
    pass


def save_rating(conn: sqlite3.Connection, candidate_id: int, score: int, tag: str | None, comment: str) -> int:
    cand = conn.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
    if cand is None:
        raise RatingError("후보를 찾을 수 없습니다.")
    if not isinstance(score, int) or not 1 <= score <= 5:
        raise RatingError("점수는 1~5 사이여야 합니다.")
    tag = tag or None
    if tag is not None and tag not in TAGS:
        raise RatingError("알 수 없는 태그입니다.")
    comment = (comment or "").strip()[:2000]
    cur = conn.execute("INSERT INTO ratings (candidate_id, score, tag, comment, rated_at) VALUES (?,?,?,?,?)",
                       (candidate_id, score, tag, comment, utcnow()))
    item_id = cand["item_id"]
    status = conn.execute("SELECT status FROM items WHERE id=?", (item_id,)).fetchone()["status"]
    if status not in ("승인", "기사화", "카드뉴스", "발행완료"):
        set_status(conn, "item", item_id, TAG_STATUS[tag], "editor")
    if tag == "follow":
        conn.execute("UPDATE items SET follow_boost=1 WHERE id=?", (item_id,))
    conn.commit()
    return cur.lastrowid


def latest_rating(conn: sqlite3.Connection, candidate_id: int):
    return conn.execute("SELECT * FROM ratings WHERE candidate_id=? ORDER BY id DESC LIMIT 1",
                        (candidate_id,)).fetchone()


class ApprovalLocked(Exception):
    pass


def approve(conn: sqlite3.Connection, item_id: int, now: datetime) -> None:
    """편집자 승인. 엠바고 해제 전에는 잠근다."""
    item = conn.execute("SELECT embargo_at, status FROM items WHERE id=?", (item_id,)).fetchone()
    if is_locked(item["embargo_at"], now):
        raise ApprovalLocked("엠바고 해제 전에는 승인할 수 없습니다.")
    if item["status"] == "폐기":
        raise ApprovalLocked("폐기한 자료입니다. 먼저 평가 태그를 바꾸세요.")
    set_status(conn, "item", item_id, "승인", "editor")
    conn.commit()
