# 구조 설계

## 권장 기술 (Claude가 환경 점검 후 바꿀 수 있다. 바꾸면 이유를 decisions.md에)

| 층 | 권장 | 이유 |
|---|---|---|
| 언어 | Python 3.11+ | IMAP(imaplib), 문서 추출, OCR 도구가 풍부 |
| 웹 | FastAPI + Jinja2 + HTMX | 화면이 단순, 별도 프론트 빌드 불필요 |
| DB | SQLite(1인) → PostgreSQL(팀) | 시작은 파일 하나, 확장은 교체 |
| 작업 예약 | APScheduler | 폴링·추천·백업을 한 프로세스에서 |
| 문서 추출 | pypdf/pdfplumber, python-docx, openpyxl, HWP는 별도 변환기 | HWP는 품질 편차가 크니 실패 시 수동 확인 |
| OCR | Tesseract(kor) 또는 AI 비전 | 비용·정확도 비교 후 선택 |
| AI | 공급자 어댑터(Anthropic 기본) | 키만 바꿔 다른 AI 사용 |
| 배포 | Docker | 로컬·서버 동일 실행 |

## 폴더 구조 (목표)

```
app/
  main.py                 웹 진입점
  settings.py             config/*.yaml + .env 읽기
  mail/
    base.py               메일 공급자 인터페이스
    imap_provider.py      IMAP 공통 구현
    naver.py, daum.py     계정별 기본값
    sample_provider.py    samples/emails 읽기 (1단계)
  ingest/
    parser.py             MIME 파싱, 인코딩 처리
    attachments.py        첨부 저장·추출·OCR
    dedupe.py             중복·버전 묶기
    embargo.py            엠바고 감지
    privacy.py            개인정보 가리기
  ai/
    provider.py           AI 공급자 어댑터
    prompts.py            prompts/*.md 불러오기
  analyze/
    classify.py           분류·추출
    plans.py              네 가지 기획
    trend.py              트렌드 집계
  recommend/
    scoring.py            점수 계산
    picker.py             후보 12 선정(탐색 2 포함)
    learning.py           평가 반영
  write/
    article.py            기사 초안 + JSON-LD
    evidence.py           근거 대조
    cardnews.py           카드뉴스 원고
    handoff.py            연계 도구 내보내기
  jobs/
    scheduler.py          폴링·추천·백업 예약
    backup.py
  web/
    routes/, templates/, static/
config/  prompts/  templates/  samples/  docs/
data/          DB 파일, 첨부 원본 (git 제외)
backups/       (git 제외)
tests/
```

## 데이터 흐름

```
[네이버 IMAP]──┐
[다음 IMAP]────┼─▶ 수집(폴링) ─▶ 파싱·첨부 추출 ─▶ 중복·버전 묶기
[샘플 메일]────┘                                   │
                                                   ▼
                                    개인정보 가리기 ─▶ AI 분류·추출
                                                   │
                         ┌─────────────────────────┼──────────────────┐
                         ▼                         ▼                  ▼
                    단일 기획              묶음 기획·트렌드        취재 질문
                         └───────────┬─────────────┴──────────────────┘
                                     ▼
                         점수 계산 ─▶ 오늘의 후보 12 (07:00)
                                     │
                                     ▼
                          편집자 평가(1~5, 태그, 코멘트) ─▶ 가중치 학습
                                     │
                                  [승인]
                                     ▼
                     기사화 작업대(초안 + 근거 대조) ─▶ 편집자 확정
                                     │
                     ┌───────────────┼───────────────┐
                     ▼               ▼               ▼
                카드뉴스 원고   콘텐츠 변환 엔지니어   그래픽 엔지니어
```

## 상태 흐름

자료(item) 상태:
`수집됨 → 분류됨 → 후보 → 평가됨 → 승인 → 기사화 → 카드뉴스 → 발행완료`
곁가지: `보류`, `폐기`, `후속취재`, `엠바고 잠김`, `수동 확인 필요`

규칙:
- `엠바고 잠김`은 해제 시각이 지나야 `승인`으로 갈 수 있다.
- `승인`과 `발행완료`는 편집자만 바꾼다.
- 모든 상태 변경은 기록한다(누가, 언제, 이전, 이후).

## 화면 목록

1. 대시보드: 오늘의 후보 12, 계정 연결 상태, 최근 수집 건수, 경고
2. 수신함: 수집된 자료 목록, 분류·엠바고·중복 필터
3. 자료 상세: 원문, 첨부, 사진, 추출 정보, 기획 4종
4. 평가: 후보 카드에 점수·태그·코멘트
5. 학습 기록: 가중치 변화, 초기화·복원
6. 기사화 작업대: 원문 | 기사 2단, 근거 표시, 수정 이력
7. 카드뉴스: 장별 원고 편집, 사진 선택, 내려받기
8. 트렌드: 기간별 키워드·분야 변화
9. 설정: 계정, 폴더, 일정, 매체, AI 공급자, 백업
10. 연결 상태: 외부 연결 표(연결됨/미연결/샘플)
