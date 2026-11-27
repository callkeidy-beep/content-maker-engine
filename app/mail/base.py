"""메일 공급자 인터페이스. IMAP·샘플 모두 이 모양을 따른다 (docs/mail-setup-naver-daum.md)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol


@dataclass
class ConnectionStep:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class ConnectionReport:
    account_id: str
    status: str                      # connected / failed / not_configured / sample
    steps: list[ConnectionStep] = field(default_factory=list)
    message: str = ""


@dataclass
class RawMessage:
    account_id: str
    folder: str
    uid: int
    raw: bytes
    source_path: str | None = None


class MailProvider(Protocol):
    account_id: str

    def test_connection(self) -> ConnectionReport: ...
    def list_folders(self) -> list[str]: ...
    def fetch_new(self, folder: str, since_uid: int) -> Iterator[RawMessage]: ...
    def uidvalidity(self, folder: str) -> int: ...
