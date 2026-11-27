# 기사 초안

## 입력
- 기획(JSON), 근거 자료 원문(문단·페이지 번호 붙음)
- 매체 설정: {{publication}}, 문체 설정: {{style}}
- 템플릿 구조: templates/article.md.j2

## 문체
- 짧은 문장. 주어와 술어가 먼저 보이게.
- 해설보다 사실. 형용사보다 숫자와 장면.
- 한 문단 2~3문장.
- 같은 대상은 끝까지 같은 이름으로 부른다.
- 금지어: {{style.avoid}}

## 구조
1. 제목: 핵심 사실 하나. 30자 안팎. 낚시 금지.
2. 부제: 제목이 못 담은 두 번째 사실.
3. 요약 3줄: 첫 줄만 읽어도 기사가 이해되게.
4. 핵심 사실 표: 언제·어디서·누가·무엇·숫자.
5. 본문: 소제목 2~4개.
6. 자주 묻는 질문(선택): 자료로 답할 수 있는 질문만. 2~4개.
7. 출처.

## 인용
- 인용문은 원문 문자열을 그대로 복사한다. 한 글자도 바꾸지 않는다.
- 원문에 인용이 없으면 인용을 쓰지 않는다.

## 출력
```json
{
  "front_matter": {
    "title": "", "subtitle": "", "category": "", "tags": [],
    "people": [], "orgs": [], "embargo_at": null
  },
  "summary": ["", "", ""],
  "fact_table": [{"label": "", "value": "", "source_ref": ""}],
  "sections": [{
    "subhead": "",
    "sentences": [{"text": "", "source_refs": [""]}]
  }],
  "faq": [{"q": "", "a": "", "source_refs": [""]}],
  "sources": [{"org": "", "received_at": "", "title": "", "attachments": []}],
  "unverified": ["근거를 찾지 못한 내용"]
}
```
문장마다 source_refs가 비어 있으면 그 문장은 쓰지 말고 unverified로 옮긴다.
