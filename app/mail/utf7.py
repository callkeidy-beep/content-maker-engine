"""IMAP 폴더 이름용 modified UTF-7 (RFC 3501). 기존 저장소 mail_connector.py에서 옮겼다."""
from __future__ import annotations

import base64


def encode_folder(value: str) -> str:
    """Encode an IMAP mailbox name using RFC 3501 modified UTF-7."""
    if not isinstance(value, str):
        raise ValueError('invalid_folder')
    output, non_ascii = [], []

    def flush():
        if non_ascii:
            encoded = base64.b64encode(''.join(non_ascii).encode('utf-16-be')).decode('ascii')
            output.append('&' + encoded.rstrip('=').replace('/', ',') + '-')
            non_ascii.clear()

    for character in value:
        if 0x20 <= ord(character) <= 0x7e:
            flush()
            output.append('&-' if character == '&' else character)
        else:
            non_ascii.append(character)
    flush()
    return ''.join(output)


def decode_folder(value: str | bytes) -> str:
    """Decode modified UTF-7; malformed input is rejected rather than guessed."""
    if isinstance(value, bytes):
        value = value.decode('ascii')
    output, position = [], 0
    while position < len(value):
        if value[position] != '&':
            if ord(value[position]) > 127:
                raise ValueError('invalid_modified_utf7')
            output.append(value[position])
            position += 1
            continue
        end = value.find('-', position)
        if end == -1:
            raise ValueError('invalid_modified_utf7')
        encoded = value[position + 1:end]
        if not encoded:
            output.append('&')
        else:
            raw = encoded.replace(',', '/')
            raw += '=' * ((4 - len(raw) % 4) % 4)
            try:
                output.append(base64.b64decode(raw, validate=True).decode('utf-16-be'))
            except (ValueError, UnicodeError) as error:
                raise ValueError('invalid_modified_utf7') from error
        position = end + 1
    return ''.join(output)


