# 근거 대조 (코드 검사 다음의 2차 검사)

코드가 먼저 한다: 인용문 문자열 일치, 숫자 값 일치.
AI는 그 다음 의미 검사만 한다.

## 입력
기사 문장 목록(각 문장의 source_refs와 그 원문 구절).

## 할 일
문장마다 판정한다.
- grounded: 원문이 이 문장을 뒷받침한다.
- partial: 일부만 뒷받침한다. 무엇이 빠졌는지 쓴다.
- ungrounded: 원문에 없다.
- distorted: 원문과 뜻이 다르다(과장, 시제·주체 바뀜).

## 출력
```json
{"checks": [{"sentence_index": 0, "verdict": "grounded|partial|ungrounded|distorted", "note": ""}]}
```
