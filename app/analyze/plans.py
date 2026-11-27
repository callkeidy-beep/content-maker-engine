"""규칙 기획. 1단계는 단일 기사와 추가 취재 질문 두 가지를 규칙으로 만든다.

- 사실 문장은 원문 문단을 그대로 옮긴다. 새 사실을 만들지 않는다.
- 묶음 기사·트렌드 분석은 AI 연결(2단계) 뒤에 만든다.
"""
from __future__ import annotations

import sqlite3

from app.db import dumps, loads


def _item(conn, item_id):
    row = conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone()
    return {k: row[k] for k in row.keys()}


def single_plan(item: dict, photo_ids: list[int]) -> dict:
    facts = loads(item["key_facts"], [])
    entities = loads(item["entities"], {})
    gaps = [s["note"] for s in entities.get("signals", [])]
    if item["kind"] == "tip":
        gaps.append("제보 내용 전체가 당사자 확인 전 주장임")
    if not photo_ids:
        gaps.append("사용 가능한 사진 없음")
    return {
        "type": "single",
        "item_ids": [str(item["id"])],
        "working_title": item["title_guess"],
        "angle": "확인 필요(규칙 기획은 앵글을 만들지 않는다. 편집자가 정한다)",
        "lead_options": [f["text"] for f in facts[:2]],
        "must_include": facts[:5],
        "gaps": gaps,
        "photo_pick": [str(p) for p in photo_ids[:1]],
        "estimated_length": "medium" if len(facts) >= 4 else "short",
    }


def questions_plan(item: dict) -> dict | None:
    entities = loads(item["entities"], {})
    signals = entities.get("signals", [])
    numbers = entities.get("numbers", [])
    percents = [n for n in numbers if n["value"].endswith("%")]
    if item["kind"] != "tip" and not signals and not percents:
        return None
    issues, questions, data = [], [], []
    for s in signals:
        issues.append({"hypothesis": f"'{s['term']}' 표현의 기준이 자료에 없다", "why": s["note"],
                       "lens": "표현의 틈", "source_ref": s["source_ref"]})
        questions.append({"to": "기관 담당자", "question": f"'{s['term']}'은 어떤 기준과 기간으로 집계했습니까?",
                          "purpose": s["note"]})
    for p in percents[:2]:
        issues.append({"hypothesis": f"비율 {p['value']}의 모수가 자료에 없을 수 있다", "why": "비율만 있고 전체 수 확인 필요",
                       "lens": "빠진 숫자", "source_ref": p["source_ref"]})
        questions.append({"to": "기관 담당자", "question": f"{p['value']}의 비교 대상과 전체 수(모수)는 얼마입니까?",
                          "purpose": "비율 검증"})
        data.append(f"{p['value']} 산출에 쓴 원자료")
    if item["kind"] == "tip":
        issues.append({"hypothesis": "제보 내용은 한쪽 당사자의 주장이다", "why": "제보자 진술만 있음",
                       "lens": "이해관계자", "source_ref": f"item{item['id']}:body:p1"})
        questions += [
            {"to": "이해관계자", "question": "제보에 나온 기관(주최·판매처)은 이 사실관계를 인정합니까? 처리 계획은 무엇입니까?",
             "purpose": "반론·사실 확인"},
            {"to": "이해관계자", "question": "같은 피해를 입은 사람 수를 확인할 자료(명단·문의 건수)가 있습니까?",
             "purpose": "피해 규모 확인"},
            {"to": "전문가", "question": "이 경우 약관·법규상 책임은 누구에게 있습니까?", "purpose": "책임 주체"},
        ]
        data.append("예매·결제 내역 등 제보 내용을 뒷받침할 자료")
    return {
        "type": "questions", "item_ids": [str(item["id"])], "hidden_issues": issues,
        "questions": questions, "data_to_request": data,
        "risk_notes": "규칙으로 만든 질문 초안이다. 취재 전 편집자가 고른다.",
    }


def make_plans(conn: sqlite3.Connection, item_id: int) -> None:
    item = _item(conn, item_id)
    photo_ids = [r["id"] for r in conn.execute("SELECT id FROM photos WHERE item_id=? AND usable='true'", (item_id,))]
    # 같은 자료의 기존 규칙 기획은 새로 만든다. 이미 후보에 걸린 기획 id 는 유지한다.
    for plan in (single_plan(item, photo_ids), questions_plan(item)):
        existing = conn.execute("SELECT id FROM plans WHERE type=? AND item_ids=?",
                                (plan["type"] if plan else None, dumps([str(item_id)]))).fetchone() if plan else None
        if plan is None:
            conn.execute("DELETE FROM plans WHERE type='questions' AND item_ids=? AND id NOT IN "
                         "(SELECT plan_id FROM candidates)", (dumps([str(item_id)]),))
            continue
        refs = sorted({f["source_ref"] for f in plan.get("must_include", [])} |
                      {i["source_ref"] for i in plan.get("hidden_issues", [])})
        values = (plan["type"], dumps(plan["item_ids"]), plan.get("working_title") or item["title_guess"],
                  plan.get("angle", ""), "", dumps(plan), dumps(refs), "rule")
        if existing:
            conn.execute("UPDATE plans SET type=?, item_ids=?, title=?, angle=?, summary=?, payload=?, "
                         "source_ref_ids=?, made_by=? WHERE id=?", values + (existing["id"],))
        else:
            conn.execute("INSERT INTO plans (type, item_ids, title, angle, summary, payload, source_ref_ids, made_by) "
                         "VALUES (?,?,?,?,?,?,?,?)", values)
