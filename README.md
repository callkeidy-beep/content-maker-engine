# 콘텐츠메이커 엔진

30년 차 기자의 책상을 코드로 옮긴다. 메일함의 보도자료와 제보를 읽고, 나누고, 오늘의 기사 후보 12개를 고른다. 마지막 판단은 사람이 한다.

## 지금 상태 — 1단계(샘플)

- 가상 샘플 메일 20건(`samples/emails/`)을 네이버·다음 두 계정에서 온 것처럼 읽는다.
- 중복은 하나로, 수정본은 v2로 묶는다. 엠바고는 잠근다. 대용량 링크는 '수동 내려받기 필요'.
- AI 없이 규칙으로 분류한다. 화면에 '규칙 분류(샘플)'로 표시한다.
- 오늘의 후보 12(추천 10 + 탐색 2), 항목별 점수, 추천 이유 한 줄.
- 1~5점·태그·코멘트 평가를 저장한다. 평가는 승인이 아니다.

실제 메일 접속, AI 분류·기사 초안, 학습, 카드뉴스, 백업은 아직 없다. 해당 버튼은 꺼 두고 이유를 적었다.

## 실행

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
```

```bash
.venv/bin/uvicorn app.main:app --port 3100
```

브라우저에서 http://localhost:3100 을 연다. Docker로는 `docker compose up --build -d`.

## 문서

- 시작 안내: [00_START_HERE.md](00_START_HERE.md) · 지시서: [01_MASTER_PROMPT.md](01_MASTER_PROMPT.md)
- 저장소 규칙과 명령: [CLAUDE.md](CLAUDE.md)
- 설계: [docs/architecture.md](docs/architecture.md) · 점수: [docs/scoring.md](docs/scoring.md) · 안전장치: [docs/journalism-rules.md](docs/journalism-rules.md)
- 완료 기준과 결과: [docs/acceptance-tests.md](docs/acceptance-tests.md) · 연결 상태: [docs/connections.md](docs/connections.md) · 결정 기록: [docs/decisions.md](docs/decisions.md)

이전 구현은 Git 태그 `legacy-before-kit-20261127`에 보존했다.
