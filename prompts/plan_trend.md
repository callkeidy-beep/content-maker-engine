# 기획 3 — 트렌드 분석

## 입력
- 기간: {{start}} ~ {{end}}
- 코드가 미리 계산한 집계: 분야별 건수(직전 기간 대비), 늘어난 키워드, 줄어든 키워드, 기관별 건수
- 자료별 핵심 사실 요약

## 할 일
- 숫자는 코드 집계만 쓴다. 직접 세거나 추정하지 않는다.
- 흐름 2~4개를 찾는다. 흐름마다 근거 자료 3건 이상.
- 근거가 3건 미만이면 '징후'로만 표시한다.
- 그래픽 엔지니어로 넘길 데이터표를 만든다(집계 숫자 그대로).

## 출력
```json
{
  "type": "trend",
  "period": {"start": "", "end": ""},
  "trends": [{
    "title": "",
    "strength": "trend|signal",
    "description": "",
    "evidence_item_ids": [],
    "counter_evidence": ""
  }],
  "graphic_tables": [{
    "title": "", "chart_hint": "bar|line|table",
    "columns": [], "rows": [], "source": "콘텐츠메이커 엔진 수신 자료 집계"
  }],
  "caveats": ["수신 자료 기준이며 업계 전체를 대표하지 않음"]
}
```
