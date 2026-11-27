"""MIME 파싱. 제목·파일명은 RFC 2047 디코딩, 본문은 charset → euc-kr → cp949 → utf-8 순서로 시도."""
from __future__ import annotations

import email
import re
import struct
from dataclasses import dataclass, field
from email import policy
from email.utils import parseaddr, parsedate_to_datetime
from datetime import timezone

FALLBACK_CHARSETS = ["euc-kr", "cp949", "utf-8"]
URL_RE = re.compile(r"https?://[^\s)>\]]+")


@dataclass
class ParsedAttachment:
    filename: str
    mime: str
    size: int
    data: bytes
    width: int | None = None
    height: int | None = None


@dataclass
class ParsedMessage:
    message_id: str
    from_name: str
    from_addr: str
    subject: str
    received_at: str            # UTC ISO
    body_text: str
    body_html: str
    charset: str
    paragraphs: list[str] = field(default_factory=list)
    attachments: list[ParsedAttachment] = field(default_factory=list)
    links: list[str] = field(default_factory=list)


def decode_bytes(data: bytes, declared: str | None) -> tuple[str, str]:
    """선언된 charset 부터 차례로 시도한다. 모두 실패하면 utf-8 대체 문자로 읽고 표시한다."""
    tried = []
    for cs in ([declared] if declared else []) + FALLBACK_CHARSETS:
        if not cs or cs in tried:
            continue
        tried.append(cs)
        try:
            return data.decode(cs), cs
        except (LookupError, UnicodeDecodeError):
            continue
    return data.decode("utf-8", errors="replace"), "utf-8(replace)"


def image_size(data: bytes, mime: str) -> tuple[int | None, int | None]:
    """JPEG·PNG 머리만 읽어 가로·세로를 얻는다. 실패하면 None."""
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            w, h = struct.unpack(">II", data[16:24])
            return w, h
        if data[:2] == b"\xff\xd8":
            i = 2
            while i < len(data) - 9:
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2):
                    h, w = struct.unpack(">HH", data[i + 5:i + 9])
                    return w, h
                seg = struct.unpack(">H", data[i + 2:i + 4])[0]
                i += 2 + seg
    except (struct.error, IndexError):
        pass
    return None, None


def split_paragraphs(text: str) -> list[str]:
    """비어 있지 않은 줄 하나를 문단 하나로 본다. 원문 문자열 그대로 둔다."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def parse_message(raw: bytes) -> ParsedMessage:
    msg = email.message_from_bytes(raw, policy=policy.default)
    name, addr = parseaddr(str(msg.get("From", "")))
    try:
        received = parsedate_to_datetime(str(msg.get("Date"))).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError):
        received = None
    body_text, body_html, charset = "", "", ""
    attachments: list[ParsedAttachment] = []
    for part in msg.walk():
        if part.is_multipart():
            continue
        filename = part.get_filename()
        ctype = part.get_content_type()
        payload = part.get_payload(decode=True) or b""
        if filename or part.get_content_disposition() == "attachment":
            att = ParsedAttachment(filename or "(이름 없음)", ctype, len(payload), payload)
            if ctype.startswith("image/"):
                att.width, att.height = image_size(payload, ctype)
            attachments.append(att)
        elif ctype == "text/plain" and not body_text:
            body_text, charset = decode_bytes(payload, part.get_content_charset())
        elif ctype == "text/html" and not body_html:
            body_html, _ = decode_bytes(payload, part.get_content_charset())
    if not body_text and body_html:
        body_text = re.sub(r"<[^>]+>", "\n", body_html)
    body_text = body_text.replace("\r\n", "\n")
    return ParsedMessage(
        message_id=str(msg.get("Message-ID", "")).strip(),
        from_name=name.strip(),
        from_addr=addr.strip().lower(),
        subject=str(msg.get("Subject", "")).strip(),
        received_at=received,
        body_text=body_text,
        body_html=body_html,
        charset=charset,
        paragraphs=split_paragraphs(body_text),
        attachments=attachments,
        links=URL_RE.findall(body_text),
    )
