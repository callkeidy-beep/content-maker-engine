"""samples/emails/*.eml 을 두 계정에서 온 것처럼 읽는다. 1단계 전용.

파일 헤더 X-Sample-Account(naver/daum), X-Sample-Folder 로 계정과 폴더를 흉내 낸다.
UID 는 계정·폴더 안에서 파일 이름 순서로 1부터 매긴다.
"""
from __future__ import annotations

import email
from email import policy
from pathlib import Path
from typing import Iterator

from .base import ConnectionReport, ConnectionStep, RawMessage

SAMPLE_UIDVALIDITY = 20261127


class SampleProvider:
    def __init__(self, account_id: str, provider: str, path: Path):
        self.account_id = account_id
        self.provider = provider          # naver / daum
        self.path = path

    def _files(self) -> list[tuple[str, Path]]:
        out = []
        for p in sorted(self.path.glob("*.eml")):
            msg = email.message_from_bytes(p.read_bytes(), policy=policy.default)
            if str(msg.get("X-Sample-Account", "")).strip() != self.provider:
                continue
            out.append((str(msg.get("X-Sample-Folder", "INBOX")), p))
        return out

    def test_connection(self) -> ConnectionReport:
        return ConnectionReport(
            account_id=self.account_id, status="sample",
            steps=[ConnectionStep("샘플 파일 읽기", True, f"{len(self._files())}건")],
            message="샘플 메일입니다. 실제 메일함에 접속하지 않았습니다.",
        )

    def list_folders(self) -> list[str]:
        return sorted({folder for folder, _ in self._files()})

    def uidvalidity(self, folder: str) -> int:
        return SAMPLE_UIDVALIDITY

    def fetch_new(self, folder: str, since_uid: int) -> Iterator[RawMessage]:
        uid = 0
        for f, p in self._files():
            if f != folder:
                continue
            uid += 1
            if uid > since_uid:
                yield RawMessage(self.account_id, folder, uid, p.read_bytes(), str(p))
