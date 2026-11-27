"""config/*.yaml 과 .env 를 읽는다. 비밀값은 여기서 꺼내 쓰기만 하고 저장·출력하지 않는다."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
KST = timezone(timedelta(hours=9))


def _load_env_file(path: Path) -> None:
    """아주 단순한 .env 읽기. 이미 있는 환경변수는 덮지 않는다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _yaml(name: str) -> dict:
    return yaml.safe_load((ROOT / "config" / name).read_text(encoding="utf-8")) or {}


@dataclass
class Settings:
    categories: dict
    scoring: dict
    schedule: dict
    mail: dict
    publication: dict
    cardnews: dict
    db_path: Path
    ai_provider: str
    ai_key_present: bool
    clock_override: datetime | None = None
    extra: dict = field(default_factory=dict)

    @property
    def sample_mode(self) -> bool:
        return self.mail.get("mode", "sample") == "sample"

    @property
    def ai_enabled(self) -> bool:
        # 1단계는 AI 호출 코드가 없다. 키가 있어도 규칙 분류로 돈다.
        return False

    def now(self) -> datetime:
        """기준 시각(UTC). 샘플 모드는 config/mail.yaml sample.clock 으로 고정한다."""
        if self.clock_override is not None:
            return self.clock_override.astimezone(timezone.utc)
        env = os.environ.get("APP_CLOCK")
        if env:
            return datetime.fromisoformat(env).astimezone(timezone.utc)
        if self.sample_mode and self.mail.get("sample", {}).get("clock"):
            return datetime.fromisoformat(self.mail["sample"]["clock"]).astimezone(timezone.utc)
        return datetime.now(timezone.utc)

    def category_name(self, key: str | None) -> str:
        if not key:
            return "미분류"
        return self.categories["categories"].get(key, {}).get("name", key)

    @property
    def default_publication(self) -> dict:
        pubs = self.publication.get("publications", [])
        default = self.publication.get("default")
        return next((p for p in pubs if p.get("id") == default), pubs[0] if pubs else {})


def load_settings(db_path: str | Path | None = None, clock: datetime | None = None) -> Settings:
    _load_env_file(ROOT / ".env")
    url = os.environ.get("DATABASE_URL", "sqlite:///data/engine.db")
    path = Path(db_path) if db_path else Path(url.replace("sqlite:///", ""))
    if not path.is_absolute():
        path = ROOT / path
    provider = os.environ.get("AI_PROVIDER", "anthropic").split("#")[0].strip() or "none"
    key_var = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "google": "GOOGLE_API_KEY"}.get(provider)
    return Settings(
        categories=_yaml("categories.yaml"),
        scoring=_yaml("scoring.yaml"),
        schedule=_yaml("schedule.yaml"),
        mail=_yaml("mail.yaml"),
        publication=_yaml("publication.yaml"),
        cardnews=_yaml("cardnews.yaml"),
        db_path=path,
        ai_provider=provider,
        ai_key_present=bool(key_var and os.environ.get(key_var)),
        clock_override=clock,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def to_kst(value: datetime | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        value = datetime.fromisoformat(value)
    return value.astimezone(KST).strftime("%Y-%m-%d %H:%M")
