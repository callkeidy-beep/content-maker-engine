"""테스트 공통. '오늘'은 2026-11-27 07:00 KST 로 고정한다 (samples/README.md)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import connect
from app.main import create_app
from app.pipeline import poll
from app.recommend.picker import pick
from app.settings import KST, load_settings

CLOCK = datetime(2026, 11, 27, 7, 0, tzinfo=KST)


@pytest.fixture
def settings(tmp_path):
    return load_settings(db_path=tmp_path / "engine.db", clock=CLOCK)


@pytest.fixture
def conn(settings):
    c = connect(settings.db_path)
    poll(c, settings)
    pick(c, settings)
    yield c
    c.close()


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as cl:
        yield cl


def item_of(conn, sample: str) -> int:
    """샘플 파일 이름(예: '01_naver')으로 자료 id 를 찾는다."""
    row = conn.execute("SELECT item_id FROM messages WHERE raw_path LIKE ?", (f"%{sample}.eml",)).fetchone()
    assert row is not None, sample
    return row["item_id"]


def message_of(conn, sample: str):
    return conn.execute("SELECT * FROM messages WHERE raw_path LIKE ?", (f"%{sample}.eml",)).fetchone()


ROOT = Path(__file__).resolve().parents[1]
