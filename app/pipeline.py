"""수집 → 파싱 → 중복·버전 묶기 → 규칙 분류 → 기획. 1단계는 SampleProvider 만 쓴다."""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app.analyze import classify as cls
from app.analyze.plans import make_plans
from app.db import dumps, loads, set_status, utcnow
from app.ingest import dedupe
from app.ingest.embargo import detect_embargo
from app.ingest.parser import parse_message, split_paragraphs
from app.ingest.privacy import mask_text
from app.mail.sample_provider import SampleProvider
from app.settings import ROOT, Settings

DOC_MIMES = {
    "application/pdf": "PDF", "application/msword": "DOC",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
    "application/x-hwp": "HWP", "application/haansofthwp": "HWP", "application/vnd.hancom.hwpx": "HWPX",
}
BIG_LINK_RE = re.compile(r"\[대용량 첨부파일\]\s*(?P<name>[^\s(]+)(?:\s*\((?P<size>[^)]+)\))?")
PHOTO_CREDIT_RE = re.compile(r"사진 출처 표기\s*:\s*(?P<who>.+?)\s*제공")


def ensure_accounts(conn: sqlite3.Connection, settings: Settings) -> None:
    for acc in settings.mail.get("accounts", []):
        status = "sample" if settings.sample_mode else ("not_configured" if not acc.get("enabled") else "failed")
        conn.execute(
            "INSERT INTO mail_accounts (id, provider, address, host, port, folders, status) VALUES (?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET provider=excluded.provider, host=excluded.host, port=excluded.port, "
            "folders=excluded.folders, status=CASE WHEN mail_accounts.status='connected' AND ?='failed' "
            "THEN mail_accounts.status ELSE excluded.status END",
            (acc["id"], acc["provider"], f"샘플 ({acc['provider']})" if settings.sample_mode else None,
             acc.get("host"), acc.get("port"), dumps(acc.get("folders", [])), status, status),
        )


def providers(settings: Settings) -> list:
    if not settings.sample_mode:
        return []          # 실 IMAP 공급자는 2단계
    path = ROOT / settings.mail.get("sample", {}).get("path", "samples/emails")
    return [SampleProvider(acc["id"], acc["provider"], path) for acc in settings.mail.get("accounts", [])]


def poll(conn: sqlite3.Connection, settings: Settings) -> dict:
    """새 메일을 가져와 messages 에 넣고, 자료(item)로 묶는다. 결과 건수를 돌려준다."""
    ensure_accounts(conn, settings)
    counts, new_ids = {}, []
    started = utcnow()
    for prov in providers(settings):
        account_cfg = next(a for a in settings.mail["accounts"] if a["id"] == prov.account_id)
        got = 0
        for folder in account_cfg.get("folders", []):
            uv = prov.uidvalidity(folder)
            state = conn.execute("SELECT * FROM mail_sync_state WHERE account_id=? AND folder=?",
                                 (prov.account_id, folder)).fetchone()
            last_uid = state["last_uid"] if state and state["uidvalidity"] == uv else 0
            for raw in prov.fetch_new(folder, last_uid):
                pm = parse_message(raw.raw)
                cur = conn.execute(
                    "INSERT OR IGNORE INTO messages (account_id, folder, uid, message_id, from_name, from_addr, "
                    "subject, received_at, body_text, body_html, raw_path, charset) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (raw.account_id, raw.folder, raw.uid, pm.message_id, pm.from_name, pm.from_addr, pm.subject,
                     pm.received_at, pm.body_text, pm.body_html,
                     str(Path(raw.source_path).relative_to(ROOT)) if raw.source_path else None, pm.charset))
                if cur.rowcount:
                    new_ids.append((cur.lastrowid, pm))
                    got += 1
                last_uid = max(last_uid, raw.uid)
            conn.execute("INSERT INTO mail_sync_state (account_id, folder, uidvalidity, last_uid) VALUES (?,?,?,?) "
                         "ON CONFLICT(account_id, folder) DO UPDATE SET uidvalidity=excluded.uidvalidity, "
                         "last_uid=excluded.last_uid", (prov.account_id, folder, uv, last_uid))
        counts[prov.account_id] = got
        conn.execute("UPDATE mail_accounts SET last_ok_at=? WHERE id=?", (utcnow(), prov.account_id))
    # 받은 순서대로 묶어야 수정본이 원본 뒤에 붙는다
    new_ids.sort(key=lambda x: (x[1].received_at or "", x[0]))
    for msg_id, pm in new_ids:
        _attach_to_item(conn, settings, msg_id, pm)
    conn.execute("INSERT INTO job_log (job, started_at, ended_at, ok, counts) VALUES ('poll',?,?,1,?)",
                 (started, utcnow(), dumps(counts)))
    conn.commit()
    return counts


def _message_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


def _attach_to_item(conn: sqlite3.Connection, settings: Settings, msg_id: int, pm) -> None:
    this = {"message_id": pm.message_id, "from_addr": pm.from_addr, "subject": pm.subject, "body_text": pm.body_text}
    # 1) 중복: 같은 Message-ID 또는 거의 같은 제목+본문
    for row in conn.execute("SELECT * FROM messages WHERE item_id IS NOT NULL AND id<>?", (msg_id,)):
        if dedupe.is_duplicate(this, _message_dict(row)):
            group = row["dup_group_id"] or row["id"]
            conn.execute("UPDATE messages SET dup_group_id=? WHERE id=?", (group, row["id"]))
            conn.execute("UPDATE messages SET dup_group_id=?, item_id=?, version=? WHERE id=?",
                         (group, row["item_id"], row["version"], msg_id))
            return
    # 2) 수정본: 같은 발신 주소 + 수정 표시/높은 유사도 → 같은 자료의 다음 버전
    marker = cls.has_revision_marker(pm.subject, pm.body_text)
    latest_rows = conn.execute(
        "SELECT m.* FROM messages m JOIN items i ON i.id=m.item_id WHERE m.version=i.current_version ORDER BY m.id"
    ).fetchall()
    for row in latest_rows:
        if row["id"] == msg_id or row["item_id"] is None:
            continue
        old = _message_dict(row)
        if dedupe.is_revision(this, old, marker):
            item_id = row["item_id"]
            version = conn.execute("SELECT current_version FROM items WHERE id=?", (item_id,)).fetchone()[0] + 1
            conn.execute("UPDATE messages SET item_id=?, version=? WHERE id=?", (item_id, version, msg_id))
            conn.execute("INSERT INTO item_versions (item_id, version, message_id, diff_summary, created_at) "
                         "VALUES (?,?,?,?,?)", (item_id, version, msg_id,
                                                dedupe.diff_summary(pm.paragraphs, split_paragraphs(old["body_text"])),
                                                pm.received_at))
            _build_item(conn, settings, item_id, msg_id, pm, version)
            return
    # 3) 새 자료
    cur = conn.execute("INSERT INTO items (status, current_version) VALUES ('수집됨', 1)")
    item_id = cur.lastrowid
    conn.execute("INSERT INTO status_log (entity, entity_id, from_status, to_status, actor, at) "
                 "VALUES ('item',?,NULL,'수집됨','system',?)", (item_id, utcnow()))
    conn.execute("UPDATE messages SET item_id=?, version=1 WHERE id=?", (item_id, msg_id))
    conn.execute("INSERT INTO item_versions (item_id, version, message_id, diff_summary, created_at) "
                 "VALUES (?,?,?,?,?)", (item_id, 1, msg_id, "최초 수신", pm.received_at))
    _build_item(conn, settings, item_id, msg_id, pm, 1)


def _build_item(conn: sqlite3.Connection, settings: Settings, item_id: int, msg_id: int, pm, version: int) -> None:
    """최신 버전 메일로 자료 내용을 (다시) 만든다."""
    folder = conn.execute("SELECT folder FROM messages WHERE id=?", (msg_id,)).fetchone()["folder"]
    key = f"item{item_id}"
    c = cls.classify(key, pm.subject, pm.from_name, folder, pm.paragraphs, settings.categories)
    emb = detect_embargo(pm.subject, pm.paragraphs, pm.received_at)

    # 근거 위치: 문단마다 하나. 원문 문자열 그대로.
    conn.execute("DELETE FROM source_refs WHERE item_id=?", (item_id,))
    conn.execute("INSERT INTO source_refs (id, item_id, origin, locator, quote) VALUES (?,?,?,?,?)",
                 (f"{key}:subject", item_id, "subject", "제목", pm.subject))
    for idx, p in enumerate(pm.paragraphs, start=1):
        conn.execute("INSERT INTO source_refs (id, item_id, origin, locator, quote) VALUES (?,?,?,?,?)",
                     (f"{key}:body:p{idx}", item_id, "body", f"본문 {idx}문단", p))

    # 첨부·사진
    manual = []
    conn.execute("DELETE FROM photos WHERE item_id=?", (item_id,))
    for att in pm.attachments:
        store = ROOT / "data" / "attachments" / str(msg_id)
        store.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[\\/:*?\"<>|]", "_", att.filename)
        (store / safe).write_bytes(att.data)
        kind = DOC_MIMES.get(att.mime)
        if att.mime.startswith("image/"):
            status = "ok"
        elif kind:
            status = "not_run"           # 문서 추출은 2단계
        else:
            status = "manual"
            manual.append(f"첨부 형식 확인 필요: {att.filename}")
        cur = conn.execute("INSERT INTO attachments (message_id, filename, mime, size, path, extract_status) "
                           "VALUES (?,?,?,?,?,?)",
                           (msg_id, att.filename, att.mime, att.size, str((store / safe).relative_to(ROOT)), status))
        if att.mime.startswith("image/"):
            press = c.kind == "press_release" and c.org
            conn.execute(
                "INSERT INTO photos (attachment_id, item_id, width, height, source, provider, caption, usage_terms, usable) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (cur.lastrowid, item_id, att.width, att.height,
                 "보도자료 첨부" if press else "출처 불명",
                 c.org if press else None,
                 f"제공: {c.org}" if press else None,
                 "보도자료 배포 사진(별도 사용 조건 표기 없음)" if press else None,
                 "true" if press else "hold"))
    for m in BIG_LINK_RE.finditer(pm.body_text):
        link = pm.links[0] if pm.links else None
        conn.execute("INSERT INTO attachments (message_id, filename, mime, size, path, extract_status, external_link) "
                     "VALUES (?,?,?,?,?,?,?)", (msg_id, m["name"], None, None, None, "link_only", link))
        manual.append(f"수동 내려받기 필요: {m['name']}" + (f" ({m['size']})" if m["size"] else ""))
    credit = PHOTO_CREDIT_RE.search(pm.body_text)
    entities = c.entities
    if credit:
        entities["photo_credit"] = credit["who"].strip()

    if c.kind == "tip":
        # 제보자 원본 연락처는 DB 에만 둔다. 화면·AI 요청에는 가린 형태만 쓴다.
        contact_name, contact_info = pm.from_name, pm.from_addr
        masked = mask_text(f"{pm.from_name} / {pm.from_addr}", [pm.from_name])
    else:
        contact_name, contact_info = c.contact_name, c.contact_info
        masked = mask_text(c.contact_info) if c.contact_info else None
    conn.execute(
        "UPDATE items SET kind=?, org=?, contact_name=?, contact_info=?, contact_masked=?, category=?, "
        "category_scores=?, classified_by='rule', title_guess=?, key_facts=?, entities=?, embargo_at=?, "
        "embargo_quote=?, current_version=?, sensitive_class=?, sensitive_hits=?, mass_distribution=?, "
        "received_at=?, manual_flags=? WHERE id=?",
        (c.kind, c.org, contact_name, contact_info, masked, c.category, dumps(c.category_scores),
         c.title_guess, dumps(c.key_facts), dumps(entities), emb.at_utc if emb else None,
         emb.quote if emb else None, version, c.sensitive_class, dumps(c.sensitive_hits), int(c.mass_distribution),
         pm.received_at, dumps(manual), item_id))
    conn.execute("UPDATE items SET entities=json_set(entities, '$.signals', json(?)) WHERE id=?",
                 (dumps(c.signals), item_id))
    set_status(conn, "item", item_id, "분류됨", "system")
    make_plans(conn, item_id)


def load_item(conn: sqlite3.Connection, item_id: int) -> dict:
    row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    d = {k: row[k] for k in row.keys()}
    d["key_facts"] = loads(d["key_facts"], [])
    d["entities"] = loads(d["entities"], {})
    d["signals"] = d["entities"].get("signals", [])
    d["manual_flags"] = loads(d["manual_flags"], [])
    d["category_scores"] = loads(d["category_scores"], {})
    d["sensitive_hits"] = loads(d["sensitive_hits"], [])
    return d


def masked_for_ai(conn: sqlite3.Connection, item_id: int, settings: Settings) -> str:
    """AI 로 보낼 본문. 제보는 가린다(기본 켜짐). 1단계는 AI 를 부르지 않고 화면 미리보기에만 쓴다."""
    item = load_item(conn, item_id)
    msg = conn.execute("SELECT * FROM messages WHERE item_id=? AND version=? ORDER BY id LIMIT 1",
                       (item_id, item["current_version"])).fetchone()
    text = msg["subject"] + "\n" + msg["body_text"]
    privacy = settings.publication.get("privacy", {})
    if item["kind"] == "tip" and privacy.get("mask_tipster_info", True):
        return mask_text(text, [msg["from_name"]])
    if item["kind"] != "tip" and privacy.get("mask_press_contact", False):
        return mask_text(text)
    return text

