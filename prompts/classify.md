# 분류·추출

## 입력
- item_id, 메일 제목, 발신자, 수신 시각, 본문(문단 번호 붙음), 첨부 추출 텍스트(페이지/셀 위치 붙음), 사진 목록
- 분류 체계: {{categories}}
- 민감 분류: {{sensitive_classes}}

## 할 일
1. 보도자료(press_release)인지 제보(tip)인지 판정한다.
2. 분류 하나를 고른다. 애매하면 가장 가까운 것 하나 + confidence를 낮게.
3. 발신 기관, 담당자, 연락처를 뽑는다.
4. 엠바고 문구를 찾는다("엠바고", "보도 시점", "~시 이후 보도", "보도유예"). 시각을 ISO 8601(KST)로.
5. 핵심 사실을 3~7개 뽑는다. 각 사실은 한 문장, 근거 위치 필수.
6. 인물·기관·장소·숫자를 뽑는다. 숫자는 값·단위·무엇의 숫자인지.
7. 사진마다 캡션·제공처를 원문에서 찾는다. 없으면 null.
8. 민감 분류에 해당하면 표시한다.
9. 일괄 배포 흔적("각 언론사 귀중", 수신자 다수)이 있으면 표시한다.

## 출력
```json
{
  "item_id": "",
  "kind": "press_release|tip",
  "category": "",
  "category_confidence": 0.0,
  "org": "",
  "contact": {"name": "", "phone": "", "email": ""},
  "embargo_at": null,
  "embargo_quote": null,
  "title_guess": "",
  "key_facts": [{"text": "", "source_ref": "item:body:p3"}],
  "entities": {
    "people": [{"name": "", "role": "", "source_ref": ""}],
    "orgs": [], "places": [],
    "numbers": [{"value": "", "unit": "", "label": "", "source_ref": ""}]
  },
  "photos": [{"photo_id": "", "caption": null, "provider": null}],
  "sensitive_class": "none",
  "mass_distribution": false,
  "notes": "확인 필요 사항"
}
```
