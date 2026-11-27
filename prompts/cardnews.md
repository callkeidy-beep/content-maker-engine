# 카드뉴스 원고

## 입력
- 확정된 기사(마크다운)
- 사용 가능 사진 목록(usable=true만)
- 설정: {{cardnews}} (장수, 글자 수, 구조)
- AI 표시 문구: {{ai_disclosure.cardnews}}

## 할 일
- 기사에 있는 사실만 쓴다. 새 정보를 더하지 않는다.
- 1장은 한 문장 훅 + 대표 사진. 질문형·과장형 훅 금지, 사실로 끌어당긴다.
- 한 장에 한 메시지.
- 숫자가 있으면 number 장을 하나 만든다.
- 마지막 장: 출처(기관), 매체 이름, AI 표시 문구.
- 제목 {{title_chars}}자, 본문 {{body_chars}}자 이내.
- 사진 캡션에 '제공: 기관명'.

## 출력
templates/cardnews.schema.json 형식의 JSON.
