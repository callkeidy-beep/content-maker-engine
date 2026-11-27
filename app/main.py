"""웹 진입점. FastAPI + Jinja2 + HTMX."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.analyze.classify import strip_numbering
from app.db import connect, loads
from app.ingest.embargo import is_locked
from app.pipeline import load_item, masked_for_ai, poll
from app.recommend.picker import RecomputeLocked, current_weights, list_candidates, pick, score_items
from app.recommend.ratings import TAGS, ApprovalLocked, RatingError, approve, latest_rating, save_rating
from app.recommend.scoring import FEATURE_NAMES
from app.settings import KST, ROOT, Settings, get_settings, to_kst

STATUS_FLOW = ["수집됨", "분류됨", "후보", "평가됨", "승인", "기사화", "카드뉴스", "발행완료"]
ACCOUNT_STATUS = {"sample": "샘플", "connected": "연결됨", "failed": "접속 실패", "not_configured": "미설정"}

# 아직 연결하지 않은 기능. 버튼은 비활성으로 두고 이유를 적는다.
DISABLED = {
    "draft": "기사 초안은 2단계(AI 연결·근거 대조) 뒤에 켭니다.",
    "bundle": "묶음 기획은 2단계(AI 연결) 뒤에 만듭니다.",
    "trend": "트렌드 분석은 2단계(AI 연결) 뒤에 만듭니다.",
    "conn_test": "실제 접속 시험은 2단계에서 켭니다. 지금은 샘플 모드입니다.",
    "learning": "가중치 학습은 3단계에서 켭니다. 지금은 평가를 저장만 합니다.",
    "settings_edit": "설정은 config/*.yaml 에서 고칩니다. 화면 편집은 나중 단계입니다.",
    "extract": "첨부 문서 추출은 2단계에서 켭니다.",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        conn = connect(settings.db_path)
        app.state.conn = conn
        if settings.sample_mode:
            poll(conn, settings)
            pick(conn, settings)
        yield
        conn.close()

    app = FastAPI(title="콘텐츠메이커 엔진", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=ROOT / "app" / "static"), name="static")
    templates = Jinja2Templates(directory=ROOT / "app" / "web" / "templates")
    env = templates.env
    env.filters["kst"] = to_kst
    env.globals.update(settings=settings, FEATURE_NAMES=FEATURE_NAMES, TAGS=TAGS, DISABLED=DISABLED,
                       ACCOUNT_STATUS=ACCOUNT_STATUS, cat_name=settings.category_name,
                       strip_numbering=strip_numbering)

    def conn(request: Request):
        return request.app.state.conn

    def base_ctx(request: Request, **kw):
        c = conn(request)
        accounts = [dict(r) for r in c.execute("SELECT * FROM mail_accounts ORDER BY id")]
        warnings = [f"{a['id']} 메일 접속 실패: {a['last_error'] or '원인 확인 필요'}"
                    for a in accounts if a["status"] == "failed"]
        return {"request": request, "now": settings.now(), "accounts": accounts, "warnings": warnings,
                "ai_label": "규칙 분류(샘플)" if not settings.ai_enabled else "AI 분류", **kw}

    def candidate_view(c, cand: dict) -> dict:
        item = load_item(c, cand["item_id"])
        rating = latest_rating(c, cand["id"])
        return {**cand, "item": item, "rating": dict(rating) if rating else None,
                "locked": is_locked(item["embargo_at"], settings.now())}

    @app.get("/", response_class=HTMLResponse)
    def dashboard(request: Request):
        c = conn(request)
        date = settings.now().astimezone(KST).date().isoformat()
        cands = [candidate_view(c, x) for x in list_candidates(c, date)]
        counts = {r["account_id"]: r["n"] for r in
                  c.execute("SELECT account_id, COUNT(*) n FROM messages GROUP BY account_id")}
        last_poll = c.execute("SELECT * FROM job_log WHERE job='poll' ORDER BY id DESC LIMIT 1").fetchone()
        rated = sum(1 for x in cands if x["rating"])
        return templates.TemplateResponse(request, "dashboard.html", base_ctx(
            request, date=date, candidates=cands, counts=counts, last_poll=last_poll, rated=rated,
            target=settings.scoring["candidates"]["total"],
            recommend_time=settings.schedule.get("recommend")))

    @app.post("/candidates/{cand_id}/rate", response_class=HTMLResponse)
    def rate(request: Request, cand_id: int, score: int = Form(...), tag: str = Form(""),
             comment: str = Form("")):
        c = conn(request)
        try:
            save_rating(c, cand_id, score, tag or None, comment)
        except RatingError as e:
            raise HTTPException(400, str(e))
        if request.headers.get("HX-Request"):
            cand = next(x for x in list_candidates(c, c.execute(
                "SELECT date FROM candidates WHERE id=?", (cand_id,)).fetchone()["date"]) if x["id"] == cand_id)
            return templates.TemplateResponse(request, "_candidate.html", base_ctx(
                request, c=candidate_view(c, cand), saved=True))
        return RedirectResponse("/", status_code=303)

    @app.post("/recommend/recompute")
    def recompute(request: Request):
        try:
            pick(conn(request), settings, force=True)
        except RecomputeLocked:
            return RedirectResponse("/?locked=1", status_code=303)
        return RedirectResponse("/", status_code=303)

    @app.get("/inbox", response_class=HTMLResponse)
    def inbox(request: Request, category: str = "", kind: str = "", flag: str = ""):
        c = conn(request)
        now = settings.now()
        items = []
        for r in c.execute("SELECT id FROM items ORDER BY received_at DESC"):
            it = load_item(c, r["id"])
            it["locked"] = is_locked(it["embargo_at"], now)
            it["dup_accounts"] = [x["account_id"] for x in c.execute(
                "SELECT DISTINCT account_id FROM messages WHERE item_id=? AND version=?",
                (it["id"], it["current_version"]))]
            if category and it["category"] != category:
                continue
            if kind and it["kind"] != kind:
                continue
            if flag == "embargo" and not it["embargo_at"]:
                continue
            if flag == "dup" and len(it["dup_accounts"]) < 2:
                continue
            if flag == "version" and it["current_version"] < 2:
                continue
            if flag == "manual" and not it["manual_flags"]:
                continue
            if flag == "sensitive" and it["sensitive_class"] == "none":
                continue
            items.append(it)
        return templates.TemplateResponse(request, "inbox.html", base_ctx(
            request, items=items, f_category=category, f_kind=kind, f_flag=flag,
            categories=settings.categories["categories"]))

    @app.get("/items/{item_id}", response_class=HTMLResponse)
    def item_detail(request: Request, item_id: int):
        c = conn(request)
        if not c.execute("SELECT 1 FROM items WHERE id=?", (item_id,)).fetchone():
            raise HTTPException(404, "자료가 없습니다.")
        it = load_item(c, item_id)
        it["locked"] = is_locked(it["embargo_at"], settings.now())
        messages = [dict(r) for r in c.execute("SELECT * FROM messages WHERE item_id=? ORDER BY version, id",
                                               (item_id,))]
        latest = next(m for m in messages if m["version"] == it["current_version"])
        versions = [dict(r) for r in c.execute("SELECT * FROM item_versions WHERE item_id=? ORDER BY version",
                                               (item_id,))]
        refs = [dict(r) for r in c.execute("SELECT * FROM source_refs WHERE item_id=? AND origin='body' "
                                           "ORDER BY rowid", (item_id,))]
        attachments = [dict(r) for r in c.execute(
            "SELECT * FROM attachments WHERE message_id=? ORDER BY id", (latest["id"],))]
        photos = [dict(r) for r in c.execute("SELECT * FROM photos WHERE item_id=?", (item_id,))]
        plans = {r["type"]: loads(r["payload"]) for r in c.execute(
            "SELECT * FROM plans WHERE item_ids=?", (f'["{item_id}"]',))}
        log = [dict(r) for r in c.execute("SELECT * FROM status_log WHERE entity='item' AND entity_id=? "
                                          "ORDER BY id", (item_id,))]
        score = next((e for e in score_items(c, settings, settings.now()) if e["item"]["id"] == item_id), None)
        return templates.TemplateResponse(request, "item.html", base_ctx(
            request, it=it, messages=messages, latest=latest, versions=versions, refs=refs,
            attachments=attachments, photos=photos, plans=plans, log=log, score=score,
            ai_preview=masked_for_ai(c, item_id, settings) if it["kind"] == "tip" else None,
            error=request.query_params.get("error")))

    @app.post("/items/{item_id}/approve")
    def approve_item(request: Request, item_id: int):
        try:
            approve(conn(request), item_id, settings.now())
        except ApprovalLocked as e:
            from urllib.parse import quote
            return RedirectResponse(f"/items/{item_id}?error={quote(str(e))}", status_code=303)
        return RedirectResponse(f"/items/{item_id}", status_code=303)

    @app.get("/connections", response_class=HTMLResponse)
    def connections(request: Request):
        return templates.TemplateResponse(request, "connections.html", base_ctx(
            request, ai_provider=settings.ai_provider, ai_key_present=settings.ai_key_present))

    @app.get("/learning", response_class=HTMLResponse)
    def learning(request: Request):
        c = conn(request)
        version, weights, bias = current_weights(c, settings)
        versions = [dict(r) for r in c.execute("SELECT * FROM weight_versions ORDER BY version DESC")]
        n = c.execute("SELECT COUNT(*) FROM ratings").fetchone()[0]
        return templates.TemplateResponse(request, "learning.html", base_ctx(
            request, weights=weights, bias=bias, versions=versions, n_ratings=n,
            min_ratings=settings.scoring["learning"]["min_ratings_before_weight_update"]))

    @app.get("/settings", response_class=HTMLResponse)
    def settings_page(request: Request):
        return templates.TemplateResponse(request, "settings.html", base_ctx(request))

    return app


app = create_app()
