"""규칙 분류·추출 (AI 없이). 결과는 화면에 '규칙 분류(샘플)'로 표시한다.

AI 분류(prompts/classify.md)는 2단계에서 같은 출력 모양으로 붙는다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CONTACT_HINTS = ("담당", "문의", "연락처")
CONTACT_RE = re.compile(r"^(?:[가-힣]+\s)?(?:담당|문의|연락처|주소|전화|이메일)")
NOTICE_PREFIX = ("※", "■ 보도 시점", "첨부:", "[대용량", "다운로드:", "사진 출처")
PHONE_RE = re.compile(r"0\d{1,2}-\d{3,4}-\d{4}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ORG_SUFFIX = re.compile(r"\s+(?:[가-힣A-Za-z]*팀|[가-힣]*국|[가-힣]*과|[가-힣]*부|사무국|커뮤니케이션|출판사)$")
NUMBER_RE = re.compile(
    r"(?<![\d.])(?:\d[\d,]*(?:\.\d+)?\s?(?:조|억|만|천)?\s?~\s?)?\d[\d,]*(?:\.\d+)?"
    r"(?:\s?(?:조|억|만|천)(?:\s?\d[\d,]*(?:\.\d+)?\s?(?:억|만|천))*)?"
    r"\s?(?:원|명|편|%|점|시간|곳|석|회|쪽|개|부작|종|MB)"
)
ROLE_RE = re.compile(r"(감독|배우|지휘자|상임지휘자|피아니스트|사진가|협연자는 피아니스트)\s+([가-힣]{2,4}?)(?:이|가|은|는|의|씨|,|\s|$)")
REVISION_MARKERS = ("[수정]", "[정정]", "수정본", "정정", "대체해 주십시오", "수정 사항")
SIGNAL_TERMS = {
    "역대": "'역대' 표현의 비교 기준 확인 필요",
    "최다": "'최다'의 집계 기준·기간 확인 필요",
    "최초": "'최초'의 근거 확인 필요",
    "1위": "순위 산정 기준 확인 필요",
    "자사 집계": "'자사 집계'의 기준과 외부 검증 여부 확인 필요",
    "돌파": "누적 집계 기준(유료·무료 포함 여부) 확인 필요",
    "개관 이래": "개관 이후 집계 방식 변경 여부 확인 필요",
}


@dataclass
class Classification:
    kind: str
    category: str
    category_scores: dict
    org: str | None
    contact_name: str | None
    contact_info: str | None
    title_guess: str
    key_facts: list = field(default_factory=list)       # [{text, source_ref}]
    entities: dict = field(default_factory=dict)
    sensitive_class: str = "none"
    sensitive_hits: list = field(default_factory=list)
    mass_distribution: bool = False
    signals: list = field(default_factory=list)          # [{term, note, source_ref}]


def _strip_exclusions(text: str, word: str, exclusions: dict) -> str:
    for longer in exclusions.get(word, []):
        text = text.replace(longer, " ")
    return text


def _hits(text: str, words: list[str], exclusions: dict) -> list[str]:
    return [w for w in words if w in _strip_exclusions(text, w, exclusions)]


def classify_category(subject: str, body: str, from_name: str, cfg: dict) -> tuple[str, dict]:
    exclusions = cfg.get("exclusions", {}) or {}
    scores = {}
    for key, cat in cfg["categories"].items():
        words = cat.get("keywords", []) or []
        score = 2 * len(_hits(subject, words, exclusions)) + len(_hits(body, words, exclusions))
        score += 2 * len([h for h in (cfg.get("org_hints", {}) or {}).get(key, []) if h in from_name])
        if score:
            scores[key] = score
    if not scores:
        return "other", {}
    order = list(cfg["categories"].keys())
    best = max(scores, key=lambda k: (scores[k], -order.index(k)))
    return best, scores


def detect_sensitive(subject: str, body: str, cfg: dict) -> tuple[str, list[str]]:
    exclusions = cfg.get("exclusions", {}) or {}
    text = subject + "\n" + body
    for key, words in (cfg.get("sensitive_classes") or {}).items():
        hits = _hits(text, words, exclusions)
        if hits:
            return key, hits
    return "none", []


def guess_org(from_name: str) -> str | None:
    if not from_name:
        return None
    return ORG_SUFFIX.sub("", from_name).strip() or from_name


def clean_title(subject: str) -> str:
    return re.sub(r"^\s*(\[[^\]]*\]\s*)+", "", subject).strip()


def is_contact_or_notice(p: str) -> bool:
    return p.startswith(NOTICE_PREFIX) or bool(CONTACT_RE.match(p)) or bool(PHONE_RE.fullmatch(p)) \
        or bool(EMAIL_RE.fullmatch(p)) or p.startswith("기자님")


def extract_contact(paragraphs: list[str]) -> tuple[str | None, str | None]:
    for i, p in enumerate(paragraphs):
        if CONTACT_RE.match(p):
            info = [p]
            info += [q for q in paragraphs[i + 1:i + 3] if PHONE_RE.search(q) or EMAIL_RE.fullmatch(q)]
            text = " / ".join(info)
            names = re.findall(r"([가-힣]{2,4})\s*(?:0\d|$)", p.split(":", 1)[-1] + " ")
            name = names[-1] if names else None
            if not name:
                tokens = re.findall(r"[가-힣]{2,4}", p.split(":", 1)[-1])
                name = tokens[-1] if tokens else None
            return name, text
    return None, None


def strip_numbering(p: str) -> str:
    return re.sub(r"^\d+\.\s*", "", p)


def classify(item_key: str, subject: str, from_name: str, folder: str, paragraphs: list[str],
             cfg: dict) -> Classification:
    body = "\n".join(paragraphs)
    kind = "tip" if folder == "제보" else "press_release"
    category, scores = classify_category(subject, body, from_name, cfg)
    sensitive, sens_hits = detect_sensitive(subject, body, cfg)
    contact_name, contact_info = extract_contact(paragraphs)

    facts, numbers, people, signals = [], [], [], []
    for idx, p in enumerate(paragraphs, start=1):
        ref = f"{item_key}:body:p{idx}"
        if p.startswith("[보도자료") or p == subject or is_contact_or_notice(p):
            continue
        if any(k in p for k in ("엠바고", "보도 시점", "보도유예")):
            continue
        if len(facts) < 7:
            facts.append({"text": strip_numbering(p), "source_ref": ref})
        for m in NUMBER_RE.finditer(p):
            numbers.append({"value": m.group(0), "source_ref": ref})
        for m in ROLE_RE.finditer(p):
            people.append({"name": m.group(2), "role": m.group(1).split()[-1], "source_ref": ref})
        for term, note in SIGNAL_TERMS.items():
            if term in p:
                signals.append({"term": term, "note": note, "source_ref": ref})
    for term, note in SIGNAL_TERMS.items():
        if term in subject and not any(s["term"] == term for s in signals):
            signals.append({"term": term, "note": note, "source_ref": f"{item_key}:subject"})
    mass = any(k in body for k in ("각 언론사 귀중", "언론사 귀중", "수신: 각 언론사"))
    org = None if kind == "tip" else guess_org(from_name)
    return Classification(
        kind=kind, category=category, category_scores=scores, org=org,
        contact_name=contact_name, contact_info=contact_info,
        title_guess=clean_title(subject), key_facts=facts,
        entities={"people": people, "orgs": [org] if org else [], "places": [], "numbers": numbers},
        sensitive_class=sensitive, sensitive_hits=sens_hits, mass_distribution=mass, signals=signals,
    )


def has_revision_marker(subject: str, body: str) -> bool:
    return any(m in subject or m in body for m in REVISION_MARKERS)
