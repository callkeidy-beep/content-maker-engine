# 기획 2 — 묶음 기사

## 입력
최근 {{window_days}}일 자료 목록(분류·추출 결과 요약).

## 할 일
- 같은 주제·업계·시기로 묶어 하나의 기사가 될 수 있는 조합을 찾는다. 2~6건.
- 억지로 묶지 않는다. 공통점이 분야 이름뿐이면 묶지 않는다.
- 묶은 이유를 한 줄로. 자료끼리 다르거나 부딪히는 지점을 적는다.
- 묶음마다 기사 구조(소제목 3~5개)를 제안한다.

## 출력
```json
{
  "bundles": [{
    "type": "bundle",
    "item_ids": [],
    "working_title": "",
    "why_together": "",
    "contrasts": [""],
    "outline": [{"subhead": "", "item_ids": [], "points": [{"text": "", "source_ref": ""}]}],
    "gaps": [""]
  }]
}
```
묶을 것이 없으면 `{"bundles": []}`.
