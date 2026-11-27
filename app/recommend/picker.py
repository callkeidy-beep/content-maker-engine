"""오늘의 후보 12: main 10(총점순) + explore 2(평가가 적거나 낮은 분야). docs/scoring.md 3절."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from app.db import dumps, loads, set_status, utcnow
from app.ingest.dedupe import quoted_titles, similarity
from app.ingest.embargo import is_locked
from app.pipeline import load_item
from app.recommend.scoring import FEATURE_NAMES, ScoreContext, score, top_feature
from app.settings import KST, Settings

EXCLUDED_STATUSES = ("승인", "기사화", "카드뉴스", "발행완료", "폐기")


class RecomputeLocked(Exception):
    """이미 평가가 붙은 날짜의 후보는 다시 계산하지 않는다 (평가 보존)."""


def current_weights(conn: sqlite3.Connection, settings: Settings) -> tuple[int, dict, dict]:
    row = conn.execute("SELECT * FROM weight_versions ORDER BY version DESC LIMIT 1").fetchone()
    if row is None:
        weights = dict(settings.scoring["weights"])
        conn.execute("INSERT INTO weight_versions (version, weights, category_bias, reason, created_at) "
                     "VALUES (1,?,?,?,?)", (dumps(weights), dumps({}), "초기값(config/scoring.yaml)", utcnow()))
        return 1, weights, {}
    return row["version"], loads(row["weights"]), loads(row["category_bias"], {})


def _duplicates(item: dict, others: list[dict], now: datetime, days: int) -> int:
    since = now - timedelta(days=days)
    count = 0
    for o in others:
        if o["id"] == item["id"] or o["category"] != item["category"]:
            continue
        if not (since <= datetime.fromisoformat(o["received_at"]) <= now):
            continue
        if quoted_titles(o["title_guess"]) & quoted_titles(item["title_guess"]) or \
                similarity(o["title_guess"], item["title_guess"]) >= 0.6:
            count += 1
    return count


def score_items(conn: sqlite3.Connection, settings: Settings, now: datetime) -> list[dict]:
    """기준 시각까지 들어온 모든 자료의 점수. 화면·선정에서 같이 쓴다."""
    version, weights, bias = current_weights(conn, settings)
    rows = [load_item(conn, r["id"]) for r in conn.execute("SELECT id FROM items WHERE received_at IS NOT NULL")]
    rows = [r for r in rows if datetime.fromisoformat(r["received_at"]) <= now]
    focus = settings.default_publication.get("focus_categories", [])
    out = []
    for item in rows:
        photos = [(p["width"], p["height"]) for p in
                  conn.execute("SELECT width, height FROM photos WHERE item_id=? AND usable='true'", (item["id"],))]
        has_table = conn.execute(
            "SELECT 1 FROM attachments a JOIN messages m ON m.id=a.message_id WHERE m.item_id=? AND m.version=? "
            "AND a.filename LIKE '%.xlsx'", (item["id"], item["current_version"])).fetchone() is not None
        ctx = ScoreContext(now=now, weights=weights, category_bias=bias, focus_categories=focus,
                           penalty_per_point=settings.scoring["duplication"]["penalty_per_point"],
                           usable_photos=photos, has_table_attachment=has_table,
                           duplicates=_duplicates(item, rows, now, settings.scoring["duplication"]["window_days"]))
        res = score(item, ctx)
        plan = conn.execute("SELECT id FROM plans WHERE type='single' AND item_ids=?",
                            (dumps([str(item["id"])]),)).fetchone()
        out.append({"item": item, "result": res, "plan_id": plan["id"] if plan else None,
                    "weights_version": version, "weights": weights})
    return out


def _category_rating_stats(conn: sqlite3.Connection, now: datetime) -> dict:
    since = (now - timedelta(days=30)).isoformat()
    stats = {}
    for r in conn.execute(
            "SELECT i.category AS cat, COUNT(*) AS n, AVG(r.score) AS avg FROM ratings r "
            "JOIN candidates c ON c.id=r.candidate_id JOIN items i ON i.id=c.item_id "
            "WHERE r.rated_at>=? GROUP BY i.category", (since,)):
        stats[r["cat"]] = (r["n"], r["avg"])
    return stats


def _reason(entry: dict, slot: str, settings: Settings) -> str:
    res, item = entry["result"], entry["item"]
    key = top_feature(res.features, entry["weights"])
    text = f"{FEATURE_NAMES[key]} {res.features[key]:g}점 — {res.notes[key]}"
    if slot == "explore":
        return f"평소와 다른 분야: {settings.category_name(item['category'])} · {text}"
    return text


def pick(conn: sqlite3.Connection, settings: Settings, now: datetime | None = None, force: bool = False) -> list[dict]:
    """후보를 고르고 candidates 에 저장한다. 이미 평가가 있는 날짜는 force 여도 다시 만들지 않는다."""
    now = now or settings.now()
    cfg = settings.scoring["candidates"]
    date = now.astimezone(KST).date().isoformat()
    existing = conn.execute("SELECT COUNT(*) FROM candidates WHERE date=?", (date,)).fetchone()[0]
    if existing:
        rated = conn.execute("SELECT COUNT(*) FROM ratings r JOIN candidates c ON c.id=r.candidate_id "
                             "WHERE c.date=?", (date,)).fetchone()[0]
        if rated:
            if force:
                raise RecomputeLocked(date)
            return list_candidates(conn, date)
        if not force:
            return list_candidates(conn, date)
        conn.execute("DELETE FROM candidates WHERE date=?", (date,))

    window_start = now - timedelta(hours=cfg["window_hours"])
    scored = [e for e in score_items(conn, settings, now)
              if e["plan_id"] and datetime.fromisoformat(e["item"]["received_at"]) >= window_start
              and e["item"]["status"] not in EXCLUDED_STATUSES]
    scored.sort(key=lambda e: (-e["result"].total, -e["result"].base, e["item"]["received_at"], e["item"]["id"]))

    main, per_cat = [], {}
    for e in scored:
        if len(main) >= cfg["main"]:
            break
        cat = e["item"]["category"]
        if per_cat.get(cat, 0) >= cfg["max_per_category_in_main"]:
            continue
        main.append(e)
        per_cat[cat] = per_cat.get(cat, 0) + 1

    chosen_ids = {e["item"]["id"] for e in main}
    rest = [e for e in scored if e["item"]["id"] not in chosen_ids]
    stats = _category_rating_stats(conn, now)
    main_cats = set(per_cat)
    by_cat = {}
    for e in sorted(rest, key=lambda e: -e["result"].base):
        by_cat.setdefault(e["item"]["category"], e)

    def explore_key(cat):
        n, avg = stats.get(cat, (0, None))
        # 1) main 에 없는 분야 먼저 2) 평가 수가 적은 분야 3) 평균 평점이 낮은 분야 4) base 점수 높은 쪽
        return (cat in main_cats, n, avg if avg is not None else 0, -by_cat[cat]["result"].base)

    explore = [by_cat[c] for c in sorted(by_cat, key=explore_key)[:cfg["explore"]]]

    picked = [("main", e) for e in main] + [("explore", e) for e in explore]
    for rank, (slot, e) in enumerate(picked, start=1):
        item = e["item"]
        flags = []
        if is_locked(item["embargo_at"], now):
            flags.append("잠김")
        if item["sensitive_class"] != "none":
            flags.append("AI 초안 제한")
        flags += item["manual_flags"]
        conn.execute(
            "INSERT INTO candidates (date, rank, plan_id, item_id, total_score, base_score, feature_scores, "
            "feature_notes, slot, reason, weights_version, flags) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (date, rank, e["plan_id"], item["id"], e["result"].total, e["result"].base, dumps(e["result"].features),
             dumps(e["result"].notes), slot, _reason(e, slot, settings), e["weights_version"], dumps(flags)))
        if item["status"] == "분류됨":
            set_status(conn, "item", item["id"], "후보", "system")
    conn.execute("INSERT INTO job_log (job, started_at, ended_at, ok, counts) VALUES ('recommend',?,?,1,?)",
                 (utcnow(), utcnow(), dumps({"date": date, "main": len(main), "explore": len(explore)})))
    conn.commit()
    return list_candidates(conn, date)


def list_candidates(conn: sqlite3.Connection, date: str) -> list[dict]:
    out = []
    for r in conn.execute("SELECT * FROM candidates WHERE date=? ORDER BY rank", (date,)):
        d = {k: r[k] for k in r.keys()}
        d["feature_scores"] = loads(d["feature_scores"], {})
        d["feature_notes"] = loads(d["feature_notes"], {})
        d["flags"] = loads(d["flags"], [])
        out.append(d)
    return out
