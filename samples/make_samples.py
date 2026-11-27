import io, sys, os, json
from email.message import EmailMessage
from email.utils import format_datetime, make_msgid
from email.header import Header
from email import policy
from datetime import datetime, timezone, timedelta
from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
import openpyxl, docx

OUT = sys.argv[1] if len(sys.argv) > 1 else "samples/emails"
os.makedirs(OUT, exist_ok=True)
KST = timezone(timedelta(hours=9))
pdfmetrics.registerFont(UnicodeCIDFont("HYSMyeongJo-Medium"))
FONT = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

def photo(label, color):
    im = Image.new("RGB", (1200, 800), color)
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(FONT, 64)
    d.text((80, 340), f"샘플 사진 · {label}", fill="white", font=f)
    b = io.BytesIO(); im.save(b, "JPEG", quality=70); return b.getvalue()

def pdf(lines):
    b = io.BytesIO(); c = canvas.Canvas(b); c.setFont("HYSMyeongJo-Medium", 12)
    y = 800
    for ln in lines:
        c.drawString(60, y, ln); y -= 22
    c.save(); return b.getvalue()

def xlsx(rows):
    wb = openpyxl.Workbook(); ws = wb.active
    for r in rows: ws.append(r)
    b = io.BytesIO(); wb.save(b); return b.getvalue()

def docx_(paras):
    d = docx.Document()
    for p in paras: d.add_paragraph(p)
    b = io.BytesIO(); d.save(b); return b.getvalue()

MSGIDS = {}
def build(n, account, folder, sender, subject, body, when, attachments=(), msgid_key=None,
          charset="utf-8", note=""):
    m = EmailMessage(policy=policy.SMTP)
    m["From"] = sender
    m["To"] = "editor@naver.com" if account == "naver" else "editor@daum.net"
    m["Subject"] = subject
    m["Date"] = format_datetime(when)
    if msgid_key and msgid_key in MSGIDS:
        mid = MSGIDS[msgid_key]
    else:
        mid = make_msgid(domain="sample.invalid")
        if msgid_key: MSGIDS[msgid_key] = mid
    m["Message-ID"] = mid
    m["X-Sample-Account"] = account
    m["X-Sample-Folder"] = folder
    m["X-Sample-Note"] = ("가상 샘플. 실존 기관·인물과 무관. " + note).strip()
    m.set_content(body, charset=charset, cte="base64" if charset != "utf-8" else "8bit")
    for fname, mime, data in attachments:
        maintype, subtype = mime.split("/")
        m.add_attachment(data, maintype=maintype, subtype=subtype, filename=fname)
    path = os.path.join(OUT, f"{n:02d}_{account}.eml")
    with open(path, "wb") as fh:
        fh.write(m.as_bytes())
    return path

D = lambda d, h, mi=0: datetime(2026, 11, d, h, mi, tzinfo=KST)

FOOT = "\n\n※ 이 메일은 콘텐츠메이커 엔진 테스트용 가상 자료입니다."

S = []
# 1, 2 중복
b1 = """[보도자료] 누리픽처스 신작 '겨울 정거장' 12월 17일 개봉

1. 누리픽처스는 장편영화 '겨울 정거장'을 12월 17일 전국 극장에서 개봉한다고 밝혔다.
2. 연출은 신인 감독 한서윤이 맡았다. 배우 오태민, 진하늘이 주연이다.
3. 영화는 폐역을 앞둔 시골 간이역의 마지막 겨울을 그린다.
4. 언론 시사회는 12월 9일 오후 2시 서울 중구 누리시네마 3관에서 열린다.
5. 한서윤 감독은 "사라지는 것들의 마지막 얼굴을 기록하고 싶었다"고 말했다.

담당: 누리픽처스 홍보팀 김다은 / 02-0000-1111 / pr@nuripictures.invalid
첨부: 포스터 1종, 스틸 1종""" + FOOT
att1 = [("겨울정거장_스틸01.jpg", "image/jpeg", photo("겨울 정거장 스틸", (40, 70, 110)))]
S.append(build(1, "naver", "보도자료", "누리픽처스 홍보팀 <pr@nuripictures.invalid>",
    "[보도자료] 누리픽처스 신작 '겨울 정거장' 12월 17일 개봉", b1, D(25, 9, 12), att1, "film1",
    note="중복 테스트: 02와 같은 메일"))
S.append(build(2, "daum", "보도자료", "누리픽처스 홍보팀 <pr@nuripictures.invalid>",
    "[보도자료] 누리픽처스 신작 '겨울 정거장' 12월 17일 개봉", b1, D(25, 9, 12), att1, "film1",
    note="중복 테스트: 01과 같은 Message-ID"))
# 3 수정본
b3 = b1.replace("12월 17일", "12월 24일").replace("[보도자료]", "[보도자료·수정]") + "\n\n※ 수정 사항: 개봉일이 12월 17일에서 12월 24일로 변경되었습니다. 앞선 자료를 이 자료로 대체해 주십시오."
S.append(build(3, "naver", "보도자료", "누리픽처스 홍보팀 <pr@nuripictures.invalid>",
    "[수정] 누리픽처스 '겨울 정거장' 개봉일 12월 24일로 변경", b3, D(26, 10, 40), att1,
    note="버전 테스트: 01의 v2"))
# 4 엠바고
S.append(build(4, "daum", "보도자료", "은하수필하모닉 <press@eunhasu-phil.invalid>",
    "[엠바고 11월 28일(토) 06:00] 은하수필하모닉 2027 신년음악회 개최",
    """■ 보도 시점: 2026년 11월 28일(토) 오전 6시 이후 보도 바랍니다.

1. 은하수필하모닉은 2027년 1월 3일 은하수아트홀에서 신년음악회를 연다.
2. 지휘는 상임지휘자 마리아 콜레가 맡는다. 협연자는 피아니스트 윤도경이다.
3. 프로그램은 베토벤 교향곡 7번과 라벨 피아노 협주곡 G장조다.
4. 티켓은 12월 1일 오전 10시 예매처에서 연다. 가격은 3만~12만 원이다.
5. 지난해 신년음악회는 2회 공연 2,400석이 모두 팔렸다.

문의: 홍보마케팅팀 박선우 02-0000-2222""" + FOOT, D(26, 15, 5),
    [("신년음악회_보도자료.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      docx_(["은하수필하모닉 2027 신년음악회", "일시: 2027년 1월 3일(일) 오후 5시", "장소: 은하수아트홀", "지휘: 마리아 콜레 / 협연: 윤도경(피아노)", "티켓: 3만~12만 원, 12월 1일 오전 10시 오픈"]))],
    note="엠바고 테스트"))
# 5 전시 PDF
S.append(build(5, "naver", "보도자료", "파란정원미술관 <info@paranmuseum.invalid>",
    "파란정원미술관, 사진가 문지호 개인전 '빛의 기록' 12월 5일 개막",
    """파란정원미술관은 12월 5일부터 2027년 3월 1일까지 사진가 문지호의 개인전 '빛의 기록'을 연다.
전시에는 1990년대부터 최근까지 찍은 사진 112점이 나온다.
관람료는 성인 1만5천 원이다. 자세한 내용은 첨부 PDF를 참고해 주십시오.

홍보 담당 이수민 031-000-3333""" + FOOT, D(25, 14, 30),
    [("빛의기록_전시개요.pdf", "application/pdf", pdf([
        "파란정원미술관 2026-2027 기획전 '빛의 기록'",
        "기간: 2026년 12월 5일 ~ 2027년 3월 1일 (월요일 휴관)",
        "작품 수: 112점 (흑백 64점, 컬러 48점)",
        "관람료: 성인 15,000원 / 청소년 10,000원",
        "작가: 문지호 (1968년생)",
        "2025년 미술관 연간 관람객: 18만 4천 명"])),
     ("빛의기록_대표작.jpg", "image/jpeg", photo("빛의 기록 대표작", (90, 60, 40)))]))
# 6 OTT
S.append(build(6, "daum", "보도자료", "모아OTT 커뮤니케이션 <news@moaott.invalid>",
    "모아OTT 오리지널 '서쪽 항구' 공개 첫 주 시청 1위",
    """모아OTT는 오리지널 드라마 '서쪽 항구'가 공개 첫 주(11월 17~23일) 자사 플랫폼 시청 순위 1위에 올랐다고 밝혔다.
첫 주 시청 시간은 420만 시간이다. 전작 '북쪽 언덕'의 첫 주 기록보다 35% 많다.
8부작이며 매주 금요일 2편씩 공개한다.

※ 시청 시간은 자사 집계 기준입니다.
문의: 커뮤니케이션팀 정해린""" + FOOT, D(25, 11, 0)))
# 7 기업 실적 엠바고 + xlsx
S.append(build(7, "naver", "보도자료", "다온전자 IR팀 <ir@daon.invalid>",
    "[보도유예: 11월 27일 12:00] 다온전자 3분기 실적 발표",
    """보도유예: 2026년 11월 27일(금) 낮 12시

다온전자는 3분기 매출 1조 2,340억 원, 영업이익 1,028억 원을 기록했다고 밝혔다.
매출은 전년 같은 기간보다 8.4% 늘었다. 영업이익은 2.1% 줄었다.
부문별 세부 수치는 첨부 엑셀 파일에 있다.

문의: IR팀 최준호 02-0000-4444""" + FOOT, D(27, 8, 0),
    [("다온전자_3분기_부문별실적.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      xlsx([["부문", "3분기 매출(억 원)", "전년 동기(억 원)", "영업이익(억 원)"],
            ["가전", 6120, 5890, 512], ["부품", 4010, 3540, 431], ["콘텐츠 기기", 2210, 1955, 85],
            ["합계", 12340, 11385, 1028]]))],
    note="엠바고 테스트 + 그래픽 엔지니어용 숫자"))
# 8 정책
S.append(build(8, "daum", "보도자료", "가람시문화재단 <press@garam-arts.invalid>",
    "가람시문화재단, 2027 예술인 창작지원 공모… 총 15억 원",
    """가람시문화재단은 2027년 예술인 창작지원 사업 공모를 12월 1일부터 12월 22일까지 받는다.
총 지원액은 15억 원이다. 올해 12억 원보다 3억 원 늘었다.
지원 분야는 시각예술, 공연예술, 문학, 다원예술 4개다.
개인은 최대 1,000만 원, 단체는 최대 3,000만 원을 받는다.

문의: 예술지원팀 한도윤 031-000-5555""" + FOOT, D(26, 9, 30)))
# 9 지역
S.append(build(9, "naver", "보도자료", "하람군청 문화관광과 <tour@haram.invalid>",
    "하람군 '얼음골 겨울축제' 1월 9일 개막",
    """하람군은 2027년 1월 9일부터 1월 25일까지 얼음골 일대에서 겨울축제를 연다.
올해로 12회째다. 지난 축제에는 관광객 31만 명이 찾았다.
얼음 썰매, 송어 잡기, 야간 빛 터널을 운영한다.

문의: 문화관광과 송지아 033-000-6666""" + FOOT, D(24, 16, 20),
    [("얼음골축제_현장.jpg", "image/jpeg", photo("얼음골 축제 현장", (30, 110, 140)))]))
# 10 제보 (개인정보)
S.append(build(10, "naver", "제보", "김민재 <minjae.reader@naver.invalid>",
    "공연 취소됐는데 환불이 한 달째 안 됩니다",
    """기자님 안녕하세요. 독자 김민재입니다.
10월 25일 예정이던 '달빛 콘서트'(주최 하늘기획)가 공연 사흘 전에 취소됐습니다.
예매처에서는 주최사가 환불금을 안 보내서 처리가 늦다고만 합니다.
제가 아는 단체 대화방에만 환불 못 받은 사람이 40명이 넘습니다.
한 명당 티켓값은 9만 9천 원이었습니다.

연락처: 010-1234-5678
주소: 서울시 가람구 은행나무로 12, 301호 (자료가 필요하면 우편으로 보내드릴 수 있습니다)""" + FOOT, D(26, 22, 14),
    note="개인정보 가리기 테스트"))
# 11 euc-kr
S.append(build(11, "daum", "보도자료", "소극장연합회 <office@sogeukjang.invalid>",
    "소극장연합회, 대학로 소극장 12곳 공동 할인전 '겨울 객석'",
    """소극장연합회는 12월 한 달 동안 대학로 소극장 12곳이 참여하는 공동 할인전 '겨울 객석'을 연다.
참여 극장의 연극 18편을 40% 할인한 값에 볼 수 있다.
연합회는 올해 소극장 평균 객석 점유율이 52%라고 밝혔다. 지난해는 47%였다.

문의: 사무국 류하진 02-0000-7777""" + FOOT, D(25, 13, 45), charset="euc-kr",
    note="인코딩 테스트: euc-kr 본문"))
# 12 사고 민감
S.append(build(12, "naver", "보도자료", "별빛아트센터 <pr@byulbit.invalid>",
    "별빛아트센터 공연 중 무대 장치 고장… 관객 안전 조치 안내",
    """별빛아트센터는 11월 25일 저녁 뮤지컬 '시계탑' 공연 중 무대 승강 장치가 멈추는 사고가 있었다고 밝혔다.
이 과정에서 배우 1명이 발목을 다쳐 병원으로 옮겨졌다. 관객 부상자는 없다.
센터는 11월 26일과 27일 공연을 취소하고 장치 안전 점검을 하고 있다.
취소 공연 관람권은 전액 환불한다.

문의: 홍보팀 강유나 02-0000-8888""" + FOOT, D(26, 8, 5),
    note="민감 분류(사고) 테스트: AI 초안 제한"))
# 13 기업 MOU
S.append(build(13, "daum", "보도자료", "다온전자 홍보팀 <pr@daon.invalid>",
    "다온전자, 가람시문화재단과 지역 공연장 음향 장비 지원 협약",
    """다온전자는 11월 26일 가람시문화재단과 지역 공연장 음향 장비 지원 협약을 맺었다.
다온전자는 3년 동안 가람시 공공 공연장 6곳에 음향 장비 8억 원어치를 지원한다.

문의: 홍보팀 윤서아 02-0000-4455""" + FOOT, D(26, 17, 30),
    [("협약식.jpg", "image/jpeg", photo("협약식", (70, 70, 70)))]))
# 14 영화제
S.append(build(14, "naver", "보도자료", "가람독립영화제 사무국 <office@garamfilmfest.invalid>",
    "제9회 가람독립영화제 12월 3일 개막… 출품작 역대 최다",
    """제9회 가람독립영화제가 12월 3일부터 8일까지 가람시 일대 극장 4곳에서 열린다.
올해 출품작은 1,284편이다. 지난해 1,051편보다 22% 늘어 역대 가장 많다.
본선에는 장편 14편, 단편 38편이 올랐다.
개막작은 다큐멘터리 '물 위의 학교'다.

문의: 사무국 오세린 031-000-9999""" + FOOT, D(24, 10, 10)))
# 15 뮤지컬 관객
S.append(build(15, "daum", "보도자료", "한길컴퍼니 <pr@hangilco.invalid>",
    "뮤지컬 '종이배' 누적 관객 10만 명 돌파",
    """한길컴퍼니는 뮤지컬 '종이배'가 11월 23일 공연으로 누적 관객 10만 명을 넘었다고 밝혔다.
지난 6월 개막한 뒤 168회 공연했다. 평균 객석 점유율은 87%다.
공연은 2027년 2월 28일까지 이어진다.

문의: 마케팅팀 서재민""" + FOOT, D(24, 15, 0),
    [("종이배_커튼콜.jpg", "image/jpeg", photo("종이배 커튼콜", (120, 50, 80)))]))
# 16 미술관 관람객 (제목 영어 섞임)
S.append(build(16, "naver", "보도자료", "가람시립미술관 <museum@garam.invalid>",
    "가람시립미술관 올해 관람객 25만 명… 개관 이래 최다",
    """가람시립미술관은 11월 24일 기준 올해 관람객이 25만 2천 명이라고 밝혔다.
2025년 한 해 관람객 19만 8천 명보다 많다. 개관 이래 가장 많은 수다.
미술관은 상반기 기획전 'Blue Hour'에만 9만 명이 들었다고 설명했다.

문의: 학예팀 이하은""" + FOOT, D(25, 16, 50)))
# 17 방송 편성
S.append(build(17, "daum", "보도자료", "가람방송 편성국 <pr@grbc.invalid>",
    "가람방송 예능 '동네 한 바퀴 반' 토요일 저녁으로 편성 이동",
    """가람방송은 예능 '동네 한 바퀴 반'을 12월 5일부터 토요일 저녁 7시로 옮긴다.
지금은 수요일 밤 10시에 방송한다.
최근 4주 평균 시청률은 4.2%다.

문의: 홍보부 문하율""" + FOOT, D(26, 11, 25)))
# 18 정책 예산
S.append(build(18, "naver", "보도자료", "가람시 문화체육국 <culture@garam.invalid>",
    "가람시, 내년 문화예산 412억 원 편성… 공연장 개보수 확대",
    """가람시는 2027년 문화 분야 예산으로 412억 원을 편성해 시의회에 제출했다.
올해 385억 원보다 7% 늘었다.
가장 많이 늘어난 항목은 공공 공연장 개보수 예산으로, 28억 원에서 46억 원이 됐다.
예산안은 12월 15일 시의회 본회의에서 확정된다.

문의: 문화정책과 김태오""" + FOOT, D(26, 14, 0),
    [("2027_문화예산_요약.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      xlsx([["항목", "2026(억 원)", "2027안(억 원)"], ["공연장 개보수", 28, 46], ["예술인 지원", 62, 70],
            ["축제·행사", 95, 92], ["도서관·문화시설 운영", 200, 204], ["합계", 385, 412]]))]))
# 19 출판
S.append(build(19, "daum", "보도자료", "바람의서재 출판사 <books@baramseojae.invalid>",
    "[신간] 극장 매표원 30년의 기록 『표를 끊는 사람』",
    """바람의서재는 극장 매표원으로 30년을 일한 정순례 씨의 에세이 『표를 끊는 사람』을 펴냈다.
1990년대 단관 극장부터 멀티플렉스까지 매표소에서 본 관객의 얼굴을 담았다.
272쪽, 1만 7천 원.

문의: 편집부 조윤""" + FOOT, D(25, 10, 5),
    [("표를끊는사람_표지.jpg", "image/jpeg", photo("신간 표지", (150, 120, 60)))]))
# 20 대용량 링크
S.append(build(20, "naver", "보도자료", "한빛배급 <pr@hanbitdist.invalid>",
    "영화 '마지막 여름 수업' 스틸컷 12종 공개 (대용량 첨부)",
    """한빛배급은 영화 '마지막 여름 수업'의 스틸컷 12종을 공개했다.
영화는 2027년 1월 개봉 예정이다.

[대용량 첨부파일] 스틸컷_12종.zip (148MB)
다운로드: https://bigfile.sample.invalid/d/abc123 (12월 10일까지)

사진 출처 표기: 한빛배급 제공
문의: 홍보팀 노유진""" + FOOT, D(26, 18, 40),
    note="대용량 링크 테스트: 수동 내려받기 필요"))

print(len(S), "files")
