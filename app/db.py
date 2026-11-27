"""SQLite 저장소. 시각은 UTC ISO 문자열로 저장한다. JSON 열은 text."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS mail_accounts (
  id TEXT PRIMARY KEY, provider TEXT, address TEXT, host TEXT, port INTEGER,
  folders TEXT, status TEXT, last_ok_at TEXT, last_error TEXT
);
CREATE TABLE IF NOT EXISTS mail_sync_state (
  account_id TEXT, folder TEXT, uidvalidity INTEGER, last_uid INTEGER,
  PRIMARY KEY (account_id, folder)
);
CREATE TABLE IF NOT EXISTS messages (
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_id TEXT, folder TEXT, uid INTEGER,
  message_id TEXT, from_name TEXT, from_addr TEXT, subject TEXT, received_at TEXT,
  body_text TEXT, body_html TEXT, raw_path TEXT, charset TEXT, dup_group_id INTEGER,
  item_id INTEGER, version INTEGER,
  UNIQUE (account_id, folder, uid)
);
CREATE TABLE IF NOT EXISTS attachments (
  id INTEGER PRIMARY KEY AUTOINCREMENT, message_id INTEGER, filename TEXT, mime TEXT,
  size INTEGER, path TEXT, extract_status TEXT, extract_text TEXT, external_link TEXT
);
CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, attachment_id INTEGER, item_id INTEGER,
  width INTEGER, height INTEGER, source TEXT, provider TEXT, caption TEXT,
  usage_terms TEXT, usable TEXT
);
CREATE TABLE IF NOT EXISTS items (
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, org TEXT, contact_name TEXT,
  contact_info TEXT, contact_masked TEXT, category TEXT, category_scores TEXT,
  classified_by TEXT, title_guess TEXT, key_facts TEXT, entities TEXT, embargo_at TEXT,
  embargo_quote TEXT, status TEXT, current_version INTEGER, sensitive_class TEXT,
  sensitive_hits TEXT, mass_distribution INTEGER DEFAULT 0, received_at TEXT,
  manual_flags TEXT, follow_boost INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS item_versions (
  item_id INTEGER, version INTEGER, message_id INTEGER, diff_summary TEXT, created_at TEXT,
  PRIMARY KEY (item_id, version)
);
CREATE TABLE IF NOT EXISTS source_refs (
  id TEXT PRIMARY KEY, item_id INTEGER, origin TEXT, attachment_id INTEGER,
  locator TEXT, quote TEXT
);
CREATE TABLE IF NOT EXISTS plans (
  id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, item_ids TEXT, title TEXT, angle TEXT,
  summary TEXT, payload TEXT, source_ref_ids TEXT, made_by TEXT
);
CREATE TABLE IF NOT EXISTS candidates (
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, rank INTEGER, plan_id INTEGER,
  item_id INTEGER, total_score REAL, base_score REAL, feature_scores TEXT,
  feature_notes TEXT, slot TEXT, reason TEXT, weights_version INTEGER, flags TEXT,
  UNIQUE (date, plan_id)
);
CREATE TABLE IF NOT EXISTS ratings (
  id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_id INTEGER, score INTEGER, tag TEXT,
  comment TEXT, rated_at TEXT
);
CREATE TABLE IF NOT EXISTS weight_versions (
  version INTEGER PRIMARY KEY, weights TEXT, category_bias TEXT, reason TEXT, created_at TEXT
);
CREATE TABLE IF NOT EXISTS status_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, entity TEXT, entity_id INTEGER,
  from_status TEXT, to_status TEXT, actor TEXT, at TEXT
);
CREATE TABLE IF NOT EXISTS job_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT, job TEXT, started_at TEXT, ended_at TEXT, ok INTEGER,
  counts TEXT, cost_estimate REAL, error TEXT
);
"""


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def loads(value, default=None):
    if value is None:
        return default
    return json.loads(value)


def set_status(conn: sqlite3.Connection, entity: str, entity_id: int, to_status: str,
               actor: str, at: str | None = None) -> None:
    """상태를 바꾸고 기록한다. 같은 상태면 아무것도 하지 않는다."""
    table = {"item": "items"}[entity]
    row = conn.execute(f"SELECT status FROM {table} WHERE id=?", (entity_id,)).fetchone()
    before = row["status"] if row else None
    if before == to_status:
        return
    conn.execute(f"UPDATE {table} SET status=? WHERE id=?", (to_status, entity_id))
    conn.execute(
        "INSERT INTO status_log (entity, entity_id, from_status, to_status, actor, at) VALUES (?,?,?,?,?,?)",
        (entity, entity_id, before, to_status, actor, at or utcnow()),
    )
