# 네이버·다음 메일 연결 (IMAP)

두 서비스 모두 Gmail 같은 전용 API가 없다. 표준 IMAP으로 연결한다.
아래 값은 2026년 11월 기준 공개 안내를 정리한 것이다. 구현 시점에 각 서비스 공식 도움말로 다시 확인한다.

## 서버 정보

| 서비스 | IMAP 서버 | 포트 | 암호화 | 사용자명 | 비밀번호 |
|---|---|---|---|---|---|
| 네이버 | imap.naver.com | 993 | SSL | 메일 주소 전체 | 애플리케이션 비밀번호 |
| 다음 | imap.daum.net | 993 | SSL | 메일 주소 전체 | 앱 비밀번호(2단계 인증 계정) 또는 계정 비밀번호 — 확인 필요 |

## 사용자가 할 일

### 네이버
1. 네이버 내 정보 → 보안설정 → 2단계 인증 켜기.
   (2025년 6월부터 외부 프로그램 연동 시 2단계 인증과 애플리케이션 비밀번호가 사실상 필수)
2. 같은 화면에서 애플리케이션 비밀번호 발급. 종류는 '기타'로, 이름은 '콘텐츠메이커'.
3. 네이버 메일 → 환경설정 → POP3/IMAP 설정 → IMAP/SMTP 사용함.
4. 메일함에 '보도자료', '제보' 폴더를 만들고 자동 분류 규칙을 건다.
5. 발급한 비밀번호를 `.env`의 `NAVER_APP_PASSWORD`에 넣는다.

### 다음
1. 다음 메일 → 설정 → IMAP/POP3 → IMAP 사용 켜기.
2. 카카오 계정 2단계 인증을 쓰면 앱 비밀번호를 발급한다.
3. 폴더와 자동 분류 규칙을 네이버와 똑같이 만든다.
4. `.env`의 `DAUM_APP_PASSWORD`에 넣는다.

## 구현 규칙

- 연결: `IMAP4_SSL(host, 993)`. 타임아웃 30초.
- 폴더 선택: `SELECT`가 아니라 `EXAMINE`(읽기 전용)으로 연다.
- 본문 가져오기: `UID FETCH <uid> (BODY.PEEK[] FLAGS)`. `RFC822`·`BODY[]`는 쓰지 않는다(읽음 표시가 붙는다).
- 금지 명령: `STORE`, `COPY`, `MOVE`, `EXPUNGE`, `DELETE`. 코드에서 아예 호출하지 않는다. 테스트로 막는다.
- 한글 폴더명: `LIST` 결과는 modified UTF-7. 디코딩해 화면에 보여주고, 선택할 때 다시 인코딩한다.
- 새 메일 찾기: `UID SEARCH UID <last_uid+1>:*`. 결과가 last_uid 하나만 오면 새 메일 없음.
- UIDVALIDITY가 바뀌면: last_uid를 0으로 돌리고 최근 N일(기본 14일)을 `SINCE`로 다시 읽어 Message-ID로 대조한다.
- 인코딩: 제목·첨부 파일명은 RFC 2047 디코딩. 본문은 charset 헤더를 따르고, 없거나 틀리면 euc-kr → cp949 → utf-8 순으로 시도한다.
- 첫 연결: 전체 메일함이 아니라 최근 N일(기본 7일)만 가져온다.
- 재시도: 실패 시 1분, 5분, 15분 뒤 재시도. 3회 실패하면 계정 상태를 `failed`로 바꾸고 화면 경고.
- 인증 실패(`AUTHENTICATIONFAILED`)는 재시도하지 않는다. 바로 경고: "앱 비밀번호를 확인하세요".
- 동시 접속: 계정당 연결 1개. 짧게 열고 닫는다.
- IDLE: 연결 후 `CAPABILITY`에 IDLE이 있으면 선택 기능으로 켤 수 있다. 29분마다 다시 건다. 실패하면 폴링으로 돌아간다.

## 접속 시험 화면

설정 화면에 '접속 시험' 버튼을 둔다. 결과를 단계별로 보여준다.
1. 서버 연결 ✓/✗
2. 로그인 ✓/✗
3. 폴더 목록 ✓/✗ (찾은 폴더 이름 표시)
4. 지정 폴더 열기 ✓/✗ (메일 수 표시)
5. 최근 메일 1건 제목 미리보기 (읽음 표시 안 됨을 확인)

모두 통과해야 상태가 '연결됨'이 된다.

## 메일 공급자 인터페이스

```python
class MailProvider(Protocol):
    def test_connection(self) -> ConnectionReport: ...
    def list_folders(self) -> list[str]: ...
    def fetch_new(self, folder: str, since_uid: int) -> Iterator[RawMessage]: ...
    def uidvalidity(self, folder: str) -> int: ...
```

`SampleProvider`도 같은 인터페이스로 `samples/emails/*.eml`을 읽는다. 1단계는 이것만 쓴다.
