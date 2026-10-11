"""Категоризация, ранжирование и подбор. Формулы — spec.md, «Механика подбора».

Сила профиля P = 0.60·T + 0.25·F + 0.15·A — «насколько объективно подтверждён кандидат»:
  T — положение θ внутри полосы грейда (тест), F — балл ФСП, A — активность в регулярных заданиях.
Соответствие потребности Score = 100·(0.40·S + 0.20·P + 0.25·G + 0.15·C):
  S — стек (подтверждённый тестом навык весит больше заявленного), G — грейд, C — условия.
Каждый фактор порождает человекочитаемую причину — так выдача объяснима для работодателя.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dictionaries import (FSP_DISCIPLINES, FSP_LEVELS, FSP_RESULTS, GRADE_BY_CODE, GRADE_CODES, GRADES,
                              SPEC_BY_CODE, SPEC_CODES, category_label, grade_cutoff, grade_index, grade_upper,
                              skill_label)
from app.models import (Application, CandidateProfile, Company, Invitation, Need, SelectionItem, TaskAssignment,
                        Vacancy, utcnow)
from app.services.nlp import TfIdf

W_T, W_F, W_A = 0.60, 0.25, 0.15
# Веса подобраны на отдельном dev-наборе валидации (seed 105), отчёт — на отложенном (docs/validation/report.md).
# Категория (точное совпадение грейда) идёт первой, как требует ТЗ: соседний грейд получает заметно меньший вклад.
W_S, W_P, W_G, W_C = 0.40, 0.20, 0.25, 0.15
GRADE_FIT = {0: 1.0, 1: 0.4, -1: 0.35}  # разница «грейд кандидата − запрошенный»
# Вклад навыка в покрытие стека: подтверждён тестом > только заявлен > заявлен, но тест его опроверг
CREDIT_VERIFIED, CREDIT_DECLARED, CREDIT_REFUTED = 1.0, 0.8, 0.3
CREDIT_UNDECLARED_VERIFIED = 0.0  # тема подтверждена тестом, но в резюме не заявлена: одиночный верный ответ — слабый сигнал
SELECTION_MIN_SCORE = 30
SELECTION_MAX = 100


def fmt_rub(v: int | None) -> str:
    return "—" if v is None else f"{v:,}".replace(",", " ") + " ₽"


# ---------------------------------------------------------------- компоненты силы профиля


def fsp_score(achievements: list[dict], now: datetime | None = None) -> tuple[float, list[dict]]:
    """F = 1 − exp(−S/1.2), S = Σ уровень × результат × 0.5^(возраст/2 года). Возвращает F и вклад каждого достижения."""
    now = now or utcnow()
    total = 0.0
    contrib = []
    for a in achievements or []:
        try:
            d = datetime.fromisoformat(str(a.get("date"))[:10])
        except ValueError:
            continue
        age_years = max((now - d).days / 365.25, 0)
        lw = FSP_LEVELS.get(a.get("level"), {"weight": 0.3})["weight"]
        rw = FSP_RESULTS.get(a.get("result"), {"weight": 0.25})["weight"]
        decay = 0.5 ** (age_years / 2)
        s = lw * rw * decay
        total += s
        contrib.append({**a, "contribution": round(s, 3)})
    contrib.sort(key=lambda x: -x["contribution"])
    return round(1 - math.exp(-total / 1.2), 4), contrib


def fsp_headline(a: dict) -> str:
    res = FSP_RESULTS.get(a.get("result"), {"label": "Участник"})["label"]
    lvl = FSP_LEVELS.get(a.get("level"), {"gen": ""})["gen"]
    year = str(a.get("date", ""))[:4]
    return f"{res} {lvl} соревнований «{a.get('event_name', '')}», {year}".replace("  ", " ")


def test_position(cand: CandidateProfile) -> float:
    if cand.grade is None or cand.theta is None:
        return 0.0
    lo, hi = grade_cutoff(cand.grade), grade_upper(cand.grade)
    return max(0.0, min(1.0, (cand.theta - lo) / (hi - lo)))


def activity_score(assignments: list[TaskAssignment], now: datetime | None = None) -> tuple[float, dict]:
    now = now or utcnow()
    done = sorted([a for a in assignments if a.status == "submitted" and a.submitted_at],
                  key=lambda a: a.submitted_at, reverse=True)[:3]
    if not done:
        return 0.0, {"count": 0}
    vals = []
    for a in done:
        s = a.auto_score or 0.0
        if a.employer_score:
            s = 0.5 * s + 0.5 * (a.employer_score - 1) / 4
        vals.append(s * 0.5 ** ((now - a.submitted_at).days / 60))
    raw = [((a.auto_score or 0) if not a.employer_score else 0.5 * (a.auto_score or 0) + 0.5 * (a.employer_score - 1) / 4) for a in done]
    return round(statistics.fmean(vals), 4), {"count": len(done), "avg": round(statistics.fmean(raw), 3)}


@dataclass
class Strength:
    P: float
    T: float
    F: float
    A: float
    fsp_items: list[dict] = field(default_factory=list)
    activity: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"P": round(self.P, 4), "T": round(self.T, 4), "F": round(self.F, 4), "A": round(self.A, 4),
                "weights": {"T": W_T, "F": W_F, "A": W_A}, "activity": self.activity}


def strength(cand: CandidateProfile, assignments: list[TaskAssignment], for_employer: bool = True) -> Strength:
    T = test_position(cand)
    F, items = fsp_score(cand.fsp_achievements or [])
    if for_employer and not (cand.privacy or {}).get("show_fsp", True):
        F, items = 0.0, []  # скрытые достижения не влияют на ранжирование, чтобы не раскрывать их косвенно
    A, act = activity_score(assignments)
    return Strength(P=W_T * T + W_F * F + W_A * A, T=T, F=F, A=A, fsp_items=items, activity=act)


# Пороги отклонения «верных ответов по теме» от ожидаемых моделью (см. testing._recompute_verified_topics)
VERIFY_MARGIN = -0.35   # подтверждено: хотя бы один верный и результат не хуже ожидаемого больше чем на 0,35·n
REFUTE_MARGIN = -0.45   # опровергнуто: ≥2 вопросов и результат хуже ожидаемого больше чем на 0,45·n


def _topic(cand: CandidateProfile, skill: str) -> dict | None:
    return (cand.verified_topics or {}).get(skill)


def topic_verified(rec: dict | None) -> bool:
    if not rec or rec["correct"] < 1:
        return False
    return rec["correct"] - rec.get("expected", rec["total"] / 2) >= VERIFY_MARGIN * rec["total"]


def topic_refuted(rec: dict | None) -> bool:
    """Тема проверялась минимум двумя вопросами, и ответы заметно хуже ожидаемых для уровня кандидата."""
    if not rec or rec["total"] < 2:
        return False
    return rec["correct"] - rec.get("expected", rec["total"] / 2) <= REFUTE_MARGIN * rec["total"]


def is_verified(cand: CandidateProfile, skill: str) -> bool:
    return topic_verified(_topic(cand, skill))


def is_refuted(cand: CandidateProfile, skill: str) -> bool:
    return topic_refuted(_topic(cand, skill))


def skill_credit(cand: CandidateProfile, skill: str) -> float:
    if skill not in (cand.stack or []):
        return CREDIT_UNDECLARED_VERIFIED if is_verified(cand, skill) else 0.0
    if is_verified(cand, skill):
        return CREDIT_VERIFIED
    return CREDIT_REFUTED if is_refuted(cand, skill) else CREDIT_DECLARED


def verified_skills(cand: CandidateProfile) -> list[str]:
    """Заявленные навыки, подтверждённые тестом. Тема, проверенная тестом, но не заявленная, в балл не идёт
    (одиночный верный ответ — слабый сигнал), поэтому и подтверждённым навыком не показывается."""
    return [s for s in (cand.stack or []) if is_verified(cand, s)]


def refuted_skills(cand: CandidateProfile) -> list[str]:
    """Заявленные навыки, по которым тест показал результат заметно хуже ожидаемого для уровня кандидата."""
    return [s for s in (cand.stack or []) if not is_verified(cand, s) and is_refuted(cand, s)]


# ---------------------------------------------------------------- видимость


def visible_candidates(db: Session, company: Company | None = None, spec: str | None = None) -> list[CandidateProfile]:
    """Кандидаты, которые могут попасть в выдачу: грейд подтверждён, есть согласие на публикацию, статус поиска
    active/open, профиль не скрыт от этой компании."""
    q = select(CandidateProfile).where(CandidateProfile.grade.is_not(None), CandidateProfile.consent_publish_at.is_not(None),
                                       CandidateProfile.job_status.in_(["active", "open"]),
                                       CandidateProfile.specialization.is_not(None))
    if spec:
        q = q.where(CandidateProfile.specialization == spec)
    out = []
    for c in db.execute(q).scalars():
        hidden = [h.strip().lower() for h in (c.privacy or {}).get("hidden_companies", []) if h.strip()]
        if company is not None and company.name.strip().lower() in hidden:
            continue
        out.append(c)
    return out


def assignments_by_candidate(db: Session, ids: list[int]) -> dict[int, list[TaskAssignment]]:
    out: dict[int, list[TaskAssignment]] = {i: [] for i in ids}
    if not ids:
        return out
    for a in db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id.in_(ids))).scalars():
        out.setdefault(a.candidate_id, []).append(a)
    return out


def contacts_unlocked(db: Session, company_id: int, candidate_id: int) -> bool:
    """Контакты раскрываются только после принятия приглашения или собственного отклика кандидата (ТЗ, п. 2.2)."""
    inv = db.execute(select(Invitation.id).where(Invitation.company_id == company_id, Invitation.candidate_id == candidate_id,
                                                 Invitation.status == "accepted")).first()
    if inv:
        return True
    app = db.execute(select(Application.id).join(Vacancy).where(Vacancy.company_id == company_id,
                                                                Application.candidate_id == candidate_id)).first()
    return bool(app)


# ---------------------------------------------------------------- соответствие потребности


@dataclass
class NeedSpec:
    specialization: str
    grade: str
    stack_must: list[str]
    stack_nice: list[str]
    work_format: list[str]
    city: str
    salary_from: int
    salary_to: int
    text: str

    @classmethod
    def from_need(cls, n: Need) -> "NeedSpec":
        return cls(n.specialization, n.grade, list(n.stack_must or []), list(n.stack_nice or []), list(n.work_format or []),
                   n.city or "", n.salary_from, n.salary_to, f"{n.title}. {n.description}. {n.team_about}")

    @classmethod
    def from_vacancy(cls, v: Vacancy) -> "NeedSpec":
        return cls(v.specialization, v.grade, list(v.stack or []), [], list(v.work_format or []), v.city or "",
                   v.salary_from, v.salary_to, f"{v.title}. {v.description}")


def candidate_text(c: CandidateProfile) -> str:
    return " ".join([c.about or "", " ".join(skill_label(s) for s in c.stack or [])])


def match(need: NeedSpec, c: CandidateProfile, st: Strength, text_sim: float = 0.0) -> dict | None:
    """Балл соответствия 0–100, вклад факторов и причины. None — кандидат вне допустимых грейдов."""
    if c.grade is None:
        return None
    diff = grade_index(c.grade) - grade_index(need.grade)
    if diff not in GRADE_FIT:
        return None
    reasons: list[dict] = []
    privacy = c.privacy or {}

    # --- S: стек
    def credit(skill: str) -> float:
        return skill_credit(c, skill)

    must_hits = [s for s in need.stack_must if credit(s) > 0]
    must_cov = (sum(credit(s) for s in need.stack_must) / len(need.stack_must)) if need.stack_must else 1.0
    nice_hits = [s for s in need.stack_nice if credit(s) > 0]
    nice_cov = (sum(credit(s) for s in need.stack_nice) / len(need.stack_nice)) if need.stack_nice else 0.0
    text_norm = min(1.0, text_sim / 0.35)
    w_nice = 0.2 if need.stack_nice else 0.0
    S = (0.7 * must_cov + w_nice * nice_cov + 0.1 * text_norm) / (0.7 + w_nice + 0.1)
    if need.stack_must:
        ver = [s for s in must_hits if is_verified(c, s)]
        txt = f"Стек: {len(must_hits)} из {len(need.stack_must)} обязательных"
        if must_hits:
            txt += f" ({', '.join(skill_label(s) for s in must_hits)})"
        if ver:
            txt += f"; подтверждено тестом: {', '.join(skill_label(s) for s in ver)}"
        reasons.append({"kind": "plus" if must_cov >= 0.6 else "minus", "text": txt})
        refuted = [s for s in must_hits if not is_verified(c, s) and is_refuted(c, s)]
        if refuted:
            reasons.append({"kind": "minus", "text": f"Заявлено, но тест не подтвердил: {', '.join(skill_label(s) for s in refuted)}"})
        missing = [s for s in need.stack_must if s not in must_hits]
        if missing:
            reasons.append({"kind": "minus", "text": f"Нет в профиле: {', '.join(skill_label(s) for s in missing)}"})
    if nice_hits:
        reasons.append({"kind": "plus", "text": f"Желательные навыки: {', '.join(skill_label(s) for s in nice_hits)}"})

    # --- P: сила профиля
    P = st.P
    grade_lbl = GRADE_BY_CODE[c.grade]["label"]
    if st.T >= 0.6:
        reasons.append({"kind": "plus", "text": f"Тест: уверенный {grade_lbl} — {round(st.T * 100)}% полосы грейда"})
    elif st.T >= 0.25:
        reasons.append({"kind": "info", "text": f"Тест: {grade_lbl} подтверждён — {round(st.T * 100)}% полосы грейда"})
    else:
        reasons.append({"kind": "info", "text": f"Тест: {grade_lbl} подтверждён у нижней границы"})
    if st.fsp_items:
        best = st.fsp_items[0]
        more = f" и ещё {len(st.fsp_items) - 1}" if len(st.fsp_items) > 1 else ""
        reasons.append({"kind": "plus", "text": f"ФСП: {fsp_headline(best)}{more}"})
    elif c.fsp_id and privacy.get("show_fsp", True):
        reasons.append({"kind": "info", "text": "ФСП ID привязан, достижений пока нет"})
    else:
        reasons.append({"kind": "info", "text": "Нет данных ФСП"})
    if st.activity.get("count"):
        reasons.append({"kind": "plus", "text": f"Регулярные задания: {st.activity['count']} решено, средняя оценка {round(st.activity['avg'] * 100)}%"})

    # --- G: грейд
    G = GRADE_FIT[diff]
    if diff == 1:
        reasons.append({"kind": "info", "text": f"Грейд на ступень выше запрошенного ({grade_lbl})"})
    elif diff == -1:
        hint = ", тест близко к следующему порогу" if st.T >= 0.7 else ""
        reasons.append({"kind": "minus", "text": f"Грейд на ступень ниже запрошенного ({grade_lbl}){hint}"})

    # --- C: условия
    if not privacy.get("show_salary", True):
        sal = 0.75
        reasons.append({"kind": "info", "text": "Ожидания по зарплате скрыты кандидатом"})
    elif c.salary_expect_min is None:
        sal = 1.0
    elif c.salary_expect_min <= need.salary_to:
        sal = 1.0
        reasons.append({"kind": "plus", "text": f"Ожидания в вилке: от {fmt_rub(c.salary_expect_min)}"})
    else:
        over = c.salary_expect_min / need.salary_to - 1
        sal = 0.5 if over <= 0.15 else 0.1
        reasons.append({"kind": "minus", "text": f"Ожидания выше вилки на {round(over * 100)}%"})
    cf = set(c.work_format or [])
    nf = set(need.work_format or [])
    if not cf or not nf or cf & nf:
        fmt_score = 1.0
    else:
        fmt_score = 0.3
        reasons.append({"kind": "minus", "text": "Формат работы не совпадает"})
    remote_ok = "remote" in (cf & nf)
    if not need.city or remote_ok:
        city_score = 1.0
    elif c.city and c.city.strip().lower() == need.city.strip().lower():
        city_score = 1.0
    elif c.relocation:
        city_score = 0.8
        reasons.append({"kind": "info", "text": "Готов к переезду"})
    else:
        city_score = 0.4
        reasons.append({"kind": "minus", "text": f"Другой город ({c.city or 'не указан'})"})
    C = 0.5 * sal + 0.3 * fmt_score + 0.2 * city_score

    score = 100 * (W_S * S + W_P * P + W_G * G + W_C * C)
    order = {"plus": 0, "minus": 1, "info": 2}
    reasons.sort(key=lambda r: order[r["kind"]])
    return {"score": round(score, 1),
            "components": {"S": round(S, 3), "P": round(P, 3), "G": round(G, 3), "C": round(C, 3),
                           "T": round(st.T, 3), "F": round(st.F, 3), "A": round(st.A, 3),
                           "text_sim": round(text_sim, 3), "must_cov": round(must_cov, 3)},
            "reasons": reasons}


def rank_for_need(db: Session, need: NeedSpec, company: Company | None) -> list[tuple[CandidateProfile, dict, Strength]]:
    pool = [c for c in visible_candidates(db, company, need.specialization)
            if c.grade and abs(grade_index(c.grade) - grade_index(need.grade)) <= 1]
    asg = assignments_by_candidate(db, [c.id for c in pool])
    tfidf = TfIdf([candidate_text(c) for c in pool])
    qv = tfidf.vec(need.text + " " + " ".join(skill_label(s) for s in need.stack_must + need.stack_nice))
    out = []
    for c in pool:
        st = strength(c, asg.get(c.id, []))
        m = match(need, c, st, TfIdf.cosine(qv, tfidf.vec(candidate_text(c))))
        if m:
            out.append((c, m, st))
    out.sort(key=lambda x: (-x[1]["score"], -x[2].P))
    return out


def recommended_categories(db: Session, need: NeedSpec, company: Company | None) -> list[dict]:
    """Основная категория, соседние по грейду и смежные специализации, где есть кандидаты с нужным стеком."""
    cats = []
    gi = grade_index(need.grade)
    all_visible = visible_candidates(db, company)
    by_cat: dict[tuple[str, str], list[CandidateProfile]] = {}
    for c in all_visible:
        by_cat.setdefault((c.specialization, c.grade), []).append(c)

    def summary(spec: str, grade: str, kind: str, note: str) -> dict:
        lst = by_cat.get((spec, grade), [])
        return {"specialization": spec, "grade": grade, "label": category_label(spec, grade), "kind": kind, "note": note,
                "count": len(lst), "with_fsp": sum(1 for c in lst if c.fsp_achievements and (c.privacy or {}).get("show_fsp", True))}

    cats.append(summary(need.specialization, need.grade, "main", "Точное совпадение специализации и грейда"))
    if gi + 1 < len(GRADES):
        cats.append(summary(need.specialization, GRADES[gi + 1]["code"], "adjacent", "Грейд выше — с запасом по опыту"))
    if gi - 1 >= 0:
        cats.append(summary(need.specialization, GRADES[gi - 1]["code"], "adjacent", "Грейд ниже — растущие кандидаты"))
    if need.stack_must:
        for spec in SPEC_CODES:
            if spec == need.specialization:
                continue
            good = [c for c in all_visible if c.specialization == spec and c.grade in GRADE_CODES
                    and abs(grade_index(c.grade) - gi) <= 1
                    and sum(1 for s in need.stack_must if s in (c.stack or [])) / len(need.stack_must) >= 0.6]
            if good:
                cats.append({"specialization": spec, "grade": need.grade, "label": f"{SPEC_BY_CODE[spec]['short']} (смежная)",
                             "kind": "related", "note": f"{len(good)} кандидатов этой специализации владеют ≥60% обязательного стека",
                             "count": len(good), "with_fsp": sum(1 for c in good if c.fsp_achievements)})
    return cats


def build_selection(db: Session, need: Need, company: Company) -> None:
    """Пересчитывает подборку по потребности, сохраняя шорт-лист (pinned) и помечая новых кандидатов."""
    prev = {si.candidate_id: si for si in db.execute(select(SelectionItem).where(SelectionItem.need_id == need.id)).scalars()}
    had_previous = bool(prev)
    ranked = rank_for_need(db, NeedSpec.from_need(need), company)
    keep_ids: set[int] = set()
    rank = 0
    for c, m, _st in ranked:
        si = prev.get(c.id)
        if (m["score"] < SELECTION_MIN_SCORE or rank >= SELECTION_MAX) and not (si and si.pinned):
            continue
        rank += 1
        keep_ids.add(c.id)
        if si is None:
            si = SelectionItem(need_id=need.id, candidate_id=c.id, pinned=False, is_new=had_previous)
            db.add(si)
        else:
            si.is_new = False
        si.score, si.components, si.reasons, si.rank = m["score"], m["components"], m["reasons"], rank
    for cid, si in prev.items():
        if cid not in keep_ids and not si.pinned:
            db.delete(si)
    need.selection_at = utcnow()
    db.commit()


# ---------------------------------------------------------------- карточки


def fsp_public(cand: CandidateProfile, for_employer: bool) -> dict:
    show = (cand.privacy or {}).get("show_fsp", True) or not for_employer
    if not cand.fsp_id:
        return {"linked": False, "visible": show, "score": 0.0, "achievements": [], "status_text": "Профиль не связан с ФСП ID"}
    if not show:
        return {"linked": True, "visible": False, "score": 0.0, "achievements": [], "status_text": "Кандидат скрыл достижения ФСП"}
    F, items = fsp_score(cand.fsp_achievements or [])
    for it in items:
        it["headline"] = fsp_headline(it)
        it["discipline_label"] = FSP_DISCIPLINES.get(it.get("discipline"), it.get("discipline"))
        it["level_label"] = FSP_LEVELS.get(it.get("level"), {}).get("label")
        it["result_label"] = FSP_RESULTS.get(it.get("result"), {}).get("label")
    return {"linked": True, "visible": True, "fsp_id": cand.fsp_id if not for_employer else None, "score": F,
            "achievements": items, "fetched_at": cand.fsp_fetched_at.isoformat() + "Z" if cand.fsp_fetched_at else None,
            "status_text": None if items else "Достижений в реестре ФСП пока нет"}


def candidate_summary(cand: CandidateProfile, st: Strength) -> dict:
    """Короткая анонимная карточка для списков (подборка, банк)."""
    privacy = cand.privacy or {}
    return {
        "id": cand.id,
        "anon_code": cand.anon_code,
        "display_name": cand.full_name if privacy.get("show_name") and cand.full_name else f"Кандидат {cand.anon_code}",
        "specialization": cand.specialization,
        "grade": cand.grade,
        "category": category_label(cand.specialization, cand.grade),
        "city": cand.city,
        "relocation": cand.relocation,
        "experience_years": cand.experience_years,
        "work_format": cand.work_format,
        "salary_expect_min": cand.salary_expect_min if privacy.get("show_salary", True) else None,
        "stack": cand.stack,
        "verified_skills": verified_skills(cand),
        "refuted_skills": refuted_skills(cand),
        "has_fsp": bool(st.fsp_items),
        "fsp_top": fsp_headline(st.fsp_items[0]) if st.fsp_items else None,
        "job_status": cand.job_status,
        "strength": st.as_dict(),
    }


def candidate_card(db: Session, cand: CandidateProfile, company: Company) -> dict:
    """Полная карточка для работодателя: анонимна до принятия приглашения или отклика."""
    st = strength(cand, assignments_by_candidate(db, [cand.id])[cand.id])
    unlocked = contacts_unlocked(db, company.id, cand.id)
    card = candidate_summary(cand, st)
    privacy = cand.privacy or {}
    asg = [a for a in assignments_by_candidate(db, [cand.id])[cand.id] if a.status == "submitted"]
    card.update({
        "about": cand.about,
        "roles": cand.roles,
        "soft_skills": cand.soft_skills,
        "industries": cand.industries,
        "theta": round(cand.theta, 2) if cand.theta is not None else None,
        "theta_se": round(cand.theta_se, 2) if cand.theta_se is not None else None,
        "grade_changed_at": cand.grade_changed_at.isoformat() + "Z" if cand.grade_changed_at else None,
        "verified_topics": [{"topic": k, "label": skill_label(k), **v, "verified": is_verified(cand, k), "refuted": is_refuted(cand, k)}
                            for k, v in sorted((cand.verified_topics or {}).items(), key=lambda kv: -kv[1]["total"])],
        "fsp": fsp_public(cand, for_employer=True),
        "tasks": [{"title": a.task.title, "kind": a.task.kind, "auto_score": a.auto_score, "employer_score": a.employer_score,
                   "submitted_at": a.submitted_at.isoformat() + "Z" if a.submitted_at else None}
                  for a in asg] if privacy.get("show_tasks", True) else [],
        "contacts_unlocked": unlocked,
        "contacts": {"full_name": cand.full_name, "email": cand.contact_email or cand.user.email, "phone": cand.phone,
                     "telegram": cand.telegram} if unlocked else None,
    })
    if unlocked and cand.full_name:
        card["display_name"] = cand.full_name
    inv = db.execute(select(Invitation).where(Invitation.company_id == company.id, Invitation.candidate_id == cand.id)
                     .order_by(Invitation.created_at.desc())).scalars().first()
    card["last_invitation"] = {"id": inv.id, "status": inv.status, "created_at": inv.created_at.isoformat() + "Z"} if inv else None
    return card


def categories_grid(db: Session, company: Company | None) -> list[dict]:
    vis = visible_candidates(db, company)
    out = []
    for s in SPEC_CODES:
        for g in GRADE_CODES:
            lst = [c for c in vis if c.specialization == s and c.grade == g]
            sal = [c.salary_expect_min for c in lst if c.salary_expect_min and (c.privacy or {}).get("show_salary", True)]
            out.append({"specialization": s, "grade": g, "label": category_label(s, g), "count": len(lst),
                        "with_fsp": sum(1 for c in lst if c.fsp_achievements and (c.privacy or {}).get("show_fsp", True)),
                        "median_salary": int(statistics.median(sal)) if sal else None})
    return out
