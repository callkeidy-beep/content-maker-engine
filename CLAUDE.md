# CLAUDE.md — 콘텐츠메이커 엔진 저장소 규칙

## 이 저장소는
보도자료·제보 메일(네이버·다음 IMAP)을 모아 분류하고, 매일 기사 후보 12개를 추천하고,
편집자 평가로 추천을 고치고, 승인된 자료를 기사 초안과 카드뉴스 원고로 만드는 시스템이다.

## 사용자
코드를 직접 쓰지 않는 기자 출신 콘텐츠 디자이너. 자연어로 수정을 요청한다.
- 답은 짧게. 무엇을 바꿨는지, 어떻게 확인하는지만 말한다.
- 기술 용어는 처음 나올 때 한 줄로 풀어 쓴다.

## 절대 규칙
1. 메일함을 바꾸지 않는다. 읽음 표시·삭제·이동 금지. `BODY.PEEK`만 쓴다.
2. 원문에 없는 인용·발언·숫자를 만들지 않는다.
3. 사람 승인 없이 송고·게시하지 않는다.
4. 비밀값(앱 비밀번호, API 키)을 코드·로그·백업·커밋에 남기지 않는다.
5. 미연동 기능을 작동하는 것처럼 보이게 하지 않는다. 샘플 화면은 '샘플' 띠.
6. `docs/journalism-rules.md`와 충돌하는 요청은 실행 전에 알린다.

## 어디를 고치나
| 요청 | 고칠 곳 |
|---|---|
| 분류 바꾸기 | `config/categories.yaml` |
| 점수 기준·가중치 | `config/scoring.yaml` |
| 수집 주기·추천 시각·백업 시각 | `config/schedule.yaml` |
| 메일 계정·폴더 | `config/mail.yaml`, `.env` |
| 매체 이름·AI 표시 문구 | `config/publication.yaml` |
| 카드뉴스 장수·비율 | `config/cardnews.yaml` |
| AI가 하는 일의 방식(문체, 기준) | `prompts/*.md` |
| 기사 모양 | `templates/article.md.j2` |

설정과 프롬프트로 해결되는 요청은 코드를 고치지 않는다.

## 작업 방식
- 변경 전: 무엇을 어디서 바꿀지 한두 줄로 말한다.
- 변경 후: 테스트를 돌린다. `docs/acceptance-tests.md` 해당 항목을 확인한다.
- 커밋 메시지는 한국어, 한 줄 요약 + 이유.
- 새 의존성을 넣으면 이유를 `docs/decisions.md`에 한 줄 남긴다.
- 설계를 바꾸면 해당 docs 파일도 같이 고친다.

## 실행
1단계(샘플) 기준. 저장소 최상위 폴더에서 실행한다.

| 할 일 | 명령 |
|---|---|
| 설치(처음 한 번) | `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt` |
| 실행 | `.venv/bin/uvicorn app.main:app --port 3100` → 브라우저에서 http://localhost:3100 |
| 테스트 | `.venv/bin/python -m pytest -q` |
| Docker 실행 | `docker compose up --build -d` → http://localhost:3100 |
| Docker 끄기 | `docker compose down` (평가 기록은 남는다. `down -v`는 기록까지 지운다) |
| 샘플 처음부터 다시 | 서버를 끄고 `data/` 폴더를 지운 뒤 다시 실행 |
| 백업 | 3단계에서 만든다 |

- 샘플 기준 시각은 `config/mail.yaml`의 `sample.clock`(2026-11-27 07:00 KST)이다. 바꾸면 추천·엠바고 판단이 그 시각 기준으로 바뀐다.
- 서버는 내 PC 안(localhost)에서만 열린다. 1단계에는 로그인이 없다.
- 이전 구현(10월 22일 지시서)은 Git 태그 `legacy-before-kit-20261127`에 있다. 다음 메일 접속 시험·암호화 저장 코드는 2단계에서 여기서 옮긴다.
