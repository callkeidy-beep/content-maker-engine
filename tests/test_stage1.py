"""1단계 완료 기준 (docs/acceptance-tests.md 1-1 ~ 1-15). 테스트 이름 앞 번호가 기준 번호다."""
from __future__ import annotations

import re
from datetime import datetime

from app.db import connect, loads
from app.ingest.embargo import is_locked
from app.pipeline import load_item, masked_for_ai
from app.recommend.picker import RecomputeLocked, list_candidates, pick
from app.settings import KST
from tests.conftest import ROOT, item_of, message_of

import pytest

EXPECTED_CATEGORY = {  # samples/README.md 기대 결과표
    "01_naver": "film", "02_daum": "film", "03_naver": "film", "04_daum": "performance",
    "05_naver": "exhibition", "06_daum": "broadcast", "07_naver": "business", "08_daum": "policy",
    "09_naver": "local", "10_naver": "performance", "11_daum": "performance", "12_naver": "performance",
    "13_daum": "business", "14_naver": "film", "15_daum": "performance", "16_naver": "exhibition",
    "17_daum": "broadcast", "18_naver": "policy", "19_daum": "other", "20_naver": "film",
}


def test_1_1_reads_all_20_samples(conn):
    assert conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 20
    counts = dict(conn.execute("SELECT account_id, COUNT(*) FROM messages GROUP BY account_id").fetchall())
    assert counts == {"naver-main": 11, "daum-main": 9}
    assert conn.execute("SELECT COUNT(*) FROM messages WHERE item_id IS NULL").fetchone()[0] == 0


def test_1_2_korean_not_broken(conn):
    for row in conn.execute("SELECT subject, from_name, body_text FROM messages"):
        for text in row:
            assert "�" not in (text or "")
    m11 = message_of(conn, "11_daum")
    assert m11["charset"] == "euc-kr"
    assert m11["subject"].startswith("소극장연합회")
    assert "겨울 객석" in m11["body_text"]
    names = {r[0] for r in conn.execute("SELECT filename FROM attachments")}
    assert {"겨울정거장_스틸01.jpg", "신년음악회_보도자료.docx", "빛의기록_전시개요.pdf",
            "2027_문화예산_요약.xlsx"} <= names


def test_1_3_duplicate_pair_grouped(conn):
    a, b = message_of(conn, "01_naver"), message_of(conn, "02_daum")
    assert a["item_id"] == b["item_id"]
    assert a["dup_group_id"] and a["dup_group_id"] == b["dup_group_id"]
    assert {a["account_id"], b["account_id"]} == {"naver-main", "daum-main"}


def test_1_4_revision_is_v2_and_latest_shown(conn):
    item_id = item_of(conn, "01_naver")
    assert item_of(conn, "03_naver") == item_id
    assert message_of(conn, "03_naver")["version"] == 2
    item = load_item(conn, item_id)
    assert item["current_version"] == 2
    facts = " ".join(f["text"] for f in item["key_facts"])
    assert "12월 24일" in facts and "12월 17일" not in facts
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 18


def test_1_5_two_embargoes_detected_and_locked(conn, settings):
    e04 = load_item(conn, item_of(conn, "04_daum"))["embargo_at"]
    e07 = load_item(conn, item_of(conn, "07_naver"))["embargo_at"]
    assert datetime.fromisoformat(e04) == datetime(2026, 11, 28, 6, 0, tzinfo=KST)
    assert datetime.fromisoformat(e07) == datetime(2026, 11, 27, 12, 0, tzinfo=KST)
    now = settings.now()
    assert is_locked(e04, now) and is_locked(e07, now)
    later = datetime(2026, 11, 27, 12, 30, tzinfo=KST)
    assert is_locked(e04, later) and not is_locked(e07, later)
    assert conn.execute("SELECT COUNT(*) FROM items WHERE embargo_at IS NOT NULL").fetchone()[0] == 2


def test_1_5_locked_shown_on_screen(client):
    html = client.get("/inbox?flag=embargo").text
    assert html.count("잠김") >= 2


def test_1_6_every_item_has_a_category(conn, settings):
    keys = set(settings.categories["categories"])
    for (cat,) in conn.execute("SELECT category FROM items"):
        assert cat in keys


def test_1_6_rule_classifier_matches_expected_table(conn):
    wrong = {s: load_item(conn, item_of(conn, s))["category"] for s, want in EXPECTED_CATEGORY.items()
             if load_item(conn, item_of(conn, s))["category"] != want}
    assert wrong == {}


def test_sensitive_only_accident_sample(conn):
    rows = dict(conn.execute("SELECT id, sensitive_class FROM items").fetchall())
    assert rows[item_of(conn, "12_naver")] == "accident"
    flagged = {k for k, v in rows.items() if v != "none"}
    assert flagged == {item_of(conn, "12_naver")}       # '문화재단' 속 '화재' 오탐 없음


def test_1_7_rule_classification_without_ai_key(conn, settings, client):
    assert settings.ai_enabled is False
    assert {r[0] for r in conn.execute("SELECT classified_by FROM items")} == {"rule"}
    assert "규칙 분류(샘플)" in client.get("/").text


def test_1_8_candidate_counts_and_slots(conn, settings):
    cands = list_candidates(conn, "2026-11-27")
    main = [c for c in cands if c["slot"] == "main"]
    explore = [c for c in cands if c["slot"] == "explore"]
    assert len(cands) <= 12 and len(main) <= 10 and len(explore) <= 2
    assert len(main) == 10 and len(explore) == 2          # 샘플은 후보 풀이 충분하다
    assert not {c["item_id"] for c in main} & {c["item_id"] for c in explore}
    cats = [load_item(conn, c["item_id"])["category"] for c in explore]
    assert len(set(cats)) == len(cats)
    ranks = [c["rank"] for c in cands]
    assert ranks == list(range(1, len(cands) + 1))
    totals = [c["total_score"] for c in main]
    assert totals == sorted(totals, reverse=True)


def test_1_8_window_and_clock(conn):
    ids = {c["item_id"] for c in list_candidates(conn, "2026-11-27")}
    assert item_of(conn, "07_naver") not in ids      # 08:00 도착 — 07:00 추천에는 없다
    for s in ("09_naver", "14_naver", "15_daum"):     # 48시간 창 밖 (11월 24일)
        assert item_of(conn, s) not in ids


def test_1_9_category_cap_in_main(conn, settings):
    cap = settings.scoring["candidates"]["max_per_category_in_main"]
    counts = {}
    for c in list_candidates(conn, "2026-11-27"):
        if c["slot"] == "main":
            cat = load_item(conn, c["item_id"])["category"]
            counts[cat] = counts.get(cat, 0) + 1
    assert max(counts.values()) <= cap


def test_1_10_scores_and_reason_present(conn, client):
    for c in list_candidates(conn, "2026-11-27"):
        assert set(c["feature_scores"]) == {"timeliness", "impact", "exclusivity", "fit", "visual", "embargo",
                                            "follow_up", "numbers", "duplication"}
        assert c["reason"] and 0 <= c["total_score"] <= 100
    html = client.get("/").text
    assert html.count('class="reason"') == 12 and "항목별 점수" in html


def test_1_11_rating_saved_and_survives_reload(client, settings):
    conn = connect(settings.db_path)
    cand = list_candidates(conn, "2026-11-27")[0]
    r = client.post(f"/candidates/{cand['id']}/rate", data={"score": "4", "tag": "follow", "comment": "후속 취재 필요"},
                    headers={"HX-Request": "true"})
    assert r.status_code == 200 and "저장됨" in r.text
    fresh = connect(settings.db_path)        # 새 연결 = 새로고침·재시작과 같다
    row = fresh.execute("SELECT * FROM ratings WHERE candidate_id=?", (cand["id"],)).fetchone()
    assert (row["score"], row["tag"], row["comment"]) == (4, "follow", "후속 취재 필요")
    assert "후속 취재 필요" in client.get("/").text
    assert load_item(fresh, cand["item_id"])["status"] == "후속취재"
    bad = client.post(f"/candidates/{cand['id']}/rate", data={"score": "9"})
    assert bad.status_code == 400


def test_1_11_rated_day_not_recomputed(conn, settings):
    cand = list_candidates(conn, "2026-11-27")[0]
    from app.recommend.ratings import save_rating
    save_rating(conn, cand["id"], 3, None, "")
    with pytest.raises(RecomputeLocked):
        pick(conn, settings, force=True)


PAGES = ["/", "/inbox", "/connections", "/learning", "/settings"]


def test_1_12_sample_band_on_every_page(client, conn):
    for url in PAGES + [f"/items/{i}" for (i,) in conn.execute("SELECT id FROM items")]:
        html = client.get(url).text
        assert 'class="sample-band"' in html, url


def test_1_13_accounts_show_sample_not_connected(client, conn):
    assert {r[0] for r in conn.execute("SELECT status FROM mail_accounts")} == {"sample"}
    for url in ("/", "/connections"):
        html = client.get(url).text
        assert "pill connected" not in html
    assert re.search(r"<b>naver</b>\s*샘플", client.get("/").text)


def test_1_15_no_forbidden_imap_commands_in_code():
    forbidden = re.compile(
        r"\.(store|copy|move|expunge)\s*\(|imap\w*\.delete\s*\(|['\"](STORE|COPY|MOVE|EXPUNGE)['\"]|"
        r"\bRFC822\b|BODY\[\]", re.IGNORECASE)
    hits = []
    for path in (ROOT / "app").rglob("*.py"):
        for no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if forbidden.search(line):
                hits.append(f"{path.relative_to(ROOT)}:{no}: {line.strip()}")
    assert hits == []


# ---- 1단계 범위 밖이지만 같이 확인해 두는 것 ----

def test_tip_privacy_mask(conn, settings):
    text = masked_for_ai(conn, item_of(conn, "10_naver"), settings)
    for raw in ("010-1234-5678", "김민재", "은행나무로 12", "minjae.reader"):
        assert raw not in text
    assert "[전화]" in text and "[주소]" in text and "[제보자]" in text
    facts = " ".join(f["text"] for f in load_item(conn, item_of(conn, "10_naver"))["key_facts"])
    assert "은행나무로" not in facts and "010-" not in facts


def test_large_link_needs_manual_download(conn):
    item = load_item(conn, item_of(conn, "20_naver"))
    assert any("수동 내려받기 필요" in f for f in item["manual_flags"])
    row = conn.execute("SELECT * FROM attachments WHERE extract_status='link_only'").fetchone()
    assert row["filename"] == "스틸컷_12종.zip" and row["external_link"].startswith("https://")


def test_approval_locked_before_embargo(client, conn):
    item_id = item_of(conn, "04_daum")
    r = client.post(f"/items/{item_id}/approve", follow_redirects=False)
    assert "error=" in r.headers["location"]
    assert load_item(conn, item_id)["status"] != "승인"


def test_sensitive_flag_on_candidate(conn):
    cand = next((c for c in list_candidates(conn, "2026-11-27") if c["item_id"] == item_of(conn, "12_naver")), None)
    if cand:
        assert "AI 초안 제한" in cand["flags"]


def test_plans_quote_source_verbatim(conn):
    for row in conn.execute("SELECT payload FROM plans WHERE type='single'"):
        plan = loads(row["payload"])
        for fact in plan["must_include"]:
            quote = conn.execute("SELECT quote FROM source_refs WHERE id=?", (fact["source_ref"],)).fetchone()
            assert quote is not None and fact["text"] in quote["quote"]
