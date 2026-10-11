"""Движок адаптивного тестирования (CAT) поверх банка параметрических шаблонов.

Жизненный цикл попытки:
  start → (выдать вопрос → принять ответ → пересчитать θ → проверить правило остановки)* → finish
На finish: решение по грейду, обновление профиля (грейд, θ, подтверждённые темы), статистика шаблонов
и детектор утечек. Правила и константы — spec.md, «Механика тестирования».
"""
from __future__ import annotations

import logging
import random
import secrets
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dictionaries import GRADE_CODES, GRADES, grade_cutoff, grade_index, skill_label
from app.models import CandidateProfile, GradeEvent, TemplateStat, TestAttempt, TestItem, utcnow
from app.services import irt
from app.services.matching import topic_refuted, topic_verified
from app.services.bank import REGISTRY, Template, templates_for_spec

log = logging.getLogger("fsp_talent.testing")

CORE_SHARE_MAX = 0.35
TOPIC_BOOST = 1.3
EXPOSURE_RATE_MAX = 0.35
EXPOSURE_PENALTY = 0.5
RANDOMESQUE_K = 4
# Языки программирования: задание на языке, которого нет в стеке кандидата, проверяет язык, а не уровень
LANG_TOPICS = {"python", "javascript", "typescript", "java", "go", "csharp", "cpp", "kotlin", "php", "rust"}
FOREIGN_LANG_PENALTY = 0.15
STOP_Z = 1.645
STOP_SE = 0.30
UPGRADE_K = 0.5  # повышение предлагается, если θ − UPGRADE_K·SE ≥ порога следующего грейда (подобрано валидацией)
LEAK_WINDOW = 60
LEAK_MIN_N = 30
LEAK_MEAN = 0.2
LEAK_Z = 3.0


# ---------------------------------------------------------------- ограничения частоты


@dataclass
class GradeAvailability:
    grade: str
    allowed: bool
    reason: str | None
    available_at: datetime | None


def _last_failed_at(db: Session, cand: CandidateProfile, grade: str) -> datetime | None:
    q = (select(func.max(TestAttempt.finished_at))
         .where(TestAttempt.candidate_id == cand.id, TestAttempt.declared_grade == grade,
                TestAttempt.specialization == cand.specialization, TestAttempt.result == "not_confirmed"))
    return db.execute(q).scalar()


def availability(db: Session, cand: CandidateProfile, now: datetime | None = None) -> list[GradeAvailability]:
    """Для каждого грейда: можно ли сейчас начать тест, а если нет — почему и когда станет можно."""
    now = now or utcnow()
    out: list[GradeAvailability] = []
    in_progress = _active_attempt(db, cand)
    for g in GRADE_CODES:
        if not cand.specialization:
            out.append(GradeAvailability(g, False, "Сначала пройдите опрос и выберите специализацию", None))
            continue
        if in_progress is not None:
            out.append(GradeAvailability(g, False, "Завершите текущий тест", None))
            continue
        if cand.grade == g:
            out.append(GradeAvailability(g, False, "Этот грейд уже подтверждён", None))
            continue
        blocked_until: datetime | None = None
        reason = None
        if cand.grade is not None and cand.grade_changed_at is not None:
            until = cand.grade_changed_at + timedelta(days=settings.grade_change_cooldown_days)
            if until > now:
                blocked_until, reason = until, f"Смена грейда — не чаще раза в {settings.grade_change_cooldown_days} дней"
        failed_at = _last_failed_at(db, cand, g)
        if failed_at is not None:
            until = failed_at + timedelta(days=settings.retest_same_grade_days)
            if until > now and (blocked_until is None or until > blocked_until):
                blocked_until, reason = until, f"Повтор теста на этот грейд — через {settings.retest_same_grade_days} дней после неудачной попытки"
        out.append(GradeAvailability(g, blocked_until is None, reason, blocked_until))
    return out


# ---------------------------------------------------------------- попытка


def _active_attempt(db: Session, cand: CandidateProfile) -> TestAttempt | None:
    att = db.execute(select(TestAttempt).where(TestAttempt.candidate_id == cand.id,
                                               TestAttempt.status == "in_progress")).scalar_one_or_none()
    if att is None:
        return None
    last = max((it.answered_at or it.served_at for it in att.items), default=att.started_at)
    if utcnow() - last > timedelta(minutes=settings.attempt_abandon_minutes):
        finish_attempt(db, att, abandoned=True)
        return None
    return att


def active_attempt(db: Session, cand: CandidateProfile) -> TestAttempt | None:
    return _active_attempt(db, cand)


def start_attempt(db: Session, cand: CandidateProfile, declared_grade: str, rng: random.Random | None = None) -> TestAttempt:
    if declared_grade not in GRADE_CODES:
        raise HTTPException(422, "Неизвестный грейд")
    av = {a.grade: a for a in availability(db, cand)}[declared_grade]
    if not av.allowed:
        detail = {"message": av.reason, "available_at": av.available_at.isoformat() if av.available_at else None}
        raise HTTPException(409, detail)
    att = TestAttempt(candidate_id=cand.id, specialization=cand.specialization, declared_grade=declared_grade,
                      focus_topics=list(cand.stack or []))
    db.add(att)
    db.flush()
    _serve_next(db, att, rng or random.Random(secrets.randbits(64)))
    db.commit()
    return att


def current_item(att: TestAttempt) -> TestItem | None:
    for it in att.items:
        if it.answered_at is None:
            return it
    return None


def _responses(att: TestAttempt) -> list[tuple[float, float, int]]:
    out = []
    for it in att.items:
        if it.answered_at is not None:
            t = REGISTRY.get(it.template_id)
            if t is not None:
                out.append((t.a, t.b, int(bool(it.is_correct))))
    return out


def _seen_recently(db: Session, att: TestAttempt) -> set[str]:
    since = utcnow() - timedelta(days=settings.seen_template_window_days)
    q = (select(TestItem.template_id).join(TestAttempt)
         .where(TestAttempt.candidate_id == att.candidate_id, TestAttempt.id != att.id, TestItem.served_at >= since))
    return set(db.execute(q).scalars())


def _exposure_rates(db: Session, spec: str) -> dict[str, float]:
    """Доля попыток, в которых показывался шаблон. Считается, когда попыток достаточно для оценки."""
    total_all = db.execute(select(func.count(TestAttempt.id)).where(TestAttempt.status != "in_progress")).scalar() or 0
    total_spec = db.execute(select(func.count(TestAttempt.id)).where(TestAttempt.status != "in_progress",
                                                                      TestAttempt.specialization == spec)).scalar() or 0
    rates: dict[str, float] = {}
    for st in db.execute(select(TemplateStat)).scalars():
        t = REGISTRY.get(st.template_id)
        if t is None:
            continue
        total = total_all if t.pool == "core" else total_spec
        if total >= 20:
            rates[st.template_id] = st.exposures / total
    return rates


def _quarantined(db: Session) -> set[str]:
    return set(db.execute(select(TemplateStat.template_id).where(TemplateStat.status == "quarantine")).scalars())


def choose_template(pool: list[Template], used: set[str], seen: set[str], quarantined: set[str],
                    theta: float, focus: set[str], n_answered: int, n_core: int,
                    exposure: dict[str, float], rng: random.Random) -> Template | None:
    """Выбор следующего шаблона: максимум информации Фишера в текущей θ с поправками (см. spec.md)."""
    cands = [t for t in pool if t.id not in used and t.id not in quarantined]
    fresh = [t for t in cands if t.id not in seen]
    if len(fresh) >= RANDOMESQUE_K:  # повторно виденные шаблоны — только если свежих не хватает
        cands = fresh
    if n_answered >= 2 and (n_core + 1) / (n_answered + 1) > CORE_SHARE_MAX:
        spec_only = [t for t in cands if t.pool != "core"]
        if spec_only:
            cands = spec_only
    if not cands:
        return None
    scored = []
    for t in cands:
        w = irt.fisher_info(theta, t.a, t.b)
        if focus and set(t.topics) & focus:
            w *= TOPIC_BOOST
        langs = set(t.topics) & LANG_TOPICS
        if langs and focus & LANG_TOPICS and not (langs & focus):
            w *= FOREIGN_LANG_PENALTY
        if exposure.get(t.id, 0.0) > EXPOSURE_RATE_MAX:
            w *= EXPOSURE_PENALTY
        scored.append((w, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    return rng.choice([t for _, t in scored[:RANDOMESQUE_K]])


def _serve_next(db: Session, att: TestAttempt, rng: random.Random) -> TestItem | None:
    answered = [it for it in att.items if it.answered_at is not None]
    if answered:
        theta = answered[-1].theta_after
    else:
        theta = grade_cutoff(att.declared_grade)  # стартуем у порога заявленного грейда
    pool = templates_for_spec(att.specialization)
    used = {it.template_id for it in att.items}
    n_core = sum(1 for it in att.items if REGISTRY.get(it.template_id) and REGISTRY[it.template_id].pool == "core")
    t = choose_template(pool, used, _seen_recently(db, att), _quarantined(db), theta, set(att.focus_topics or []),
                        len(answered), n_core, _exposure_rates(db, att.specialization), rng)
    if t is None:
        return None
    for _ in range(8):  # редкие вырожденные комбинации параметров: просто берём другое зерно
        seed = rng.randrange(2**31)
        try:
            inst = t.generate(seed)
            break
        except ValueError as e:
            log.warning("Шаблон %s: %s", t.id, e)
    else:
        return None
    item = TestItem(attempt_id=att.id, template_id=t.id, seed=seed, order=len(att.items) + 1,
                    payload=inst.stored_payload(), correct_index=inst.correct_index, served_at=utcnow())
    db.add(item)
    att.items.append(item)
    db.flush()
    return item


def stop_rule(declared: str, theta: float, se: float, n: int,
              min_items: int | None = None, max_items: int | None = None) -> bool:
    """Правило остановки CAT. Тест идёт, пока решение не стало статистически уверенным относительно порога
    заявленного грейда И (если кандидат выше него) порога следующего грейда — иначе сильный кандидат выходит
    из теста с большой погрешностью и не может честно получить повышение."""
    min_items = settings.test_min_items if min_items is None else min_items
    max_items = settings.test_max_items if max_items is None else max_items
    if n >= max_items:
        return True
    if n < min_items:
        return False
    if se <= STOP_SE:
        return True
    i = grade_index(declared)
    cuts = [GRADES[i]["cutoff"]]
    if theta >= cuts[0] and i + 1 < len(GRADES):
        cuts.append(GRADES[i + 1]["cutoff"])
    return all(abs(theta - c) >= STOP_Z * se for c in cuts)


def should_stop(att: TestAttempt, theta: float, se: float, n: int) -> bool:
    return stop_rule(att.declared_grade, theta, se, n)


def submit_answer(db: Session, att: TestAttempt, item_id: int, answer_index: int,
                  rng: random.Random | None = None, now: datetime | None = None) -> TestAttempt:
    if att.status != "in_progress":
        raise HTTPException(409, "Тест уже завершён")
    item = current_item(att)
    if item is None or item.id != item_id:
        raise HTTPException(409, "Ответ на этот вопрос уже принят или вопрос не текущий")
    if not (-1 <= answer_index < len(item.payload["options"])):
        raise HTTPException(422, "Некорректный номер варианта")
    now = now or utcnow()
    elapsed = (now - item.served_at).total_seconds()
    item.answered_at = now
    item.answer_index = answer_index
    item.time_ms = int(elapsed * 1000)
    item.timed_out = elapsed > settings.item_time_limit_sec + settings.item_time_grace_sec
    if answer_index == -1:  # время вышло, вариант не выбран
        item.timed_out = True
    item.is_correct = (answer_index == item.correct_index) and not item.timed_out
    theta, se = irt.eap(_responses(att))
    item.theta_after, item.se_after = theta, se
    n = sum(1 for it in att.items if it.answered_at is not None)
    if should_stop(att, theta, se, n) or _serve_next(db, att, rng or random.Random(secrets.randbits(64))) is None:
        finish_attempt(db, att)
    db.commit()
    return att


# ---------------------------------------------------------------- завершение и решение по грейду


def decide(declared: str, theta: float, se: float) -> tuple[str, str | None, str | None]:
    """Возвращает (result, upgrade_grade, suggested_grade). Грейд не понижается принудительно:
    при неудаче только предлагается грейд ниже, который θ уже подтверждает."""
    i = grade_index(declared)
    if theta >= grade_cutoff(declared):
        if i + 1 < len(GRADES) and theta - UPGRADE_K * se >= GRADES[i + 1]["cutoff"]:
            return "confirmed_plus", GRADES[i + 1]["code"], None
        return "confirmed", None, None
    suggested = None
    for g in GRADES[:i]:
        if theta >= g["cutoff"]:
            suggested = g["code"]
    if suggested is None and i > 0:
        suggested = GRADES[0]["code"]
    return "not_confirmed", None, suggested


def _recompute_verified_topics(db: Session, cand: CandidateProfile) -> None:
    """Сводка по темам теста: сколько вопросов, сколько верных и сколько верных ОЖИДАЛОСЬ по модели при итоговой θ.

    В адаптивном тесте вопросы подбираются под уровень, поэтому верных ответов около половины у всех — «доля верных»
    по теме почти ничего не говорит. Информативно отклонение от ожидания: ответил по теме хуже, чем предсказывает
    модель для человека его уровня, — значит, тема слабее остальных."""
    q = (select(TestItem, TestAttempt.theta).join(TestAttempt)
         .where(TestAttempt.candidate_id == cand.id, TestAttempt.specialization == cand.specialization,
                TestAttempt.theta.is_not(None), TestItem.answered_at.is_not(None)))
    topics: dict[str, dict] = {}
    for it, theta in db.execute(q).all():
        t = REGISTRY.get(it.template_id)
        if t is None:
            continue
        p = float(irt.p_correct(theta, t.a, t.b))
        for topic in t.topics:
            rec = topics.setdefault(topic, {"correct": 0, "total": 0, "expected": 0.0})
            rec["total"] += 1
            rec["correct"] += int(bool(it.is_correct))
            rec["expected"] = round(rec["expected"] + p, 3)
    cand.verified_topics = topics


def _update_template_stats(db: Session, att: TestAttempt, theta: float) -> None:
    """Статистика шаблонов + детектор утечек: если по шаблону систематически отвечают лучше, чем
    предсказывает модель для людей такого уровня, — шаблон, вероятно, «слит» (известен приём решения)."""
    for it in att.items:
        if it.answered_at is None:
            continue
        t = REGISTRY.get(it.template_id)
        if t is None:
            continue
        st = db.get(TemplateStat, it.template_id)
        if st is None:
            st = TemplateStat(template_id=it.template_id, exposures=0, correct=0, residuals=[], status="active")
            db.add(st)
        u = int(bool(it.is_correct))
        st.exposures += 1
        st.correct += u
        res = list(st.residuals or [])
        res.append(round(u - float(irt.p_correct(theta, t.a, t.b)), 4))
        st.residuals = res[-LEAK_WINDOW:]
        if st.status == "active" and leak_suspected(st.residuals):
            st.status = "quarantine"
            st.flagged_at = utcnow()


def leak_suspected(residuals: list[float]) -> bool:
    n = len(residuals)
    if n < LEAK_MIN_N:
        return False
    mean = statistics.fmean(residuals)
    sd = statistics.pstdev(residuals) or 1e-6
    z = mean / (sd / n**0.5)
    return mean > LEAK_MEAN and z > LEAK_Z


def finish_attempt(db: Session, att: TestAttempt, abandoned: bool = False) -> None:
    responses = _responses(att)
    # Неотвеченный выданный вопрос в прерванной попытке не учитываем — он просто удаляется из попытки
    for it in list(att.items):
        if it.answered_at is None:
            att.items.remove(it)
            db.delete(it)
    theta, se = irt.eap(responses) if responses else (0.0, irt.PRIOR_SD)
    att.theta, att.se, att.n_items = theta, se, len(responses)
    att.finished_at = utcnow()
    cand = db.get(CandidateProfile, att.candidate_id)
    if abandoned and len(responses) < settings.test_min_items:
        att.status = "abandoned"
        att.result = "not_confirmed"
        _, _, att.suggested_grade = decide(att.declared_grade, theta, se)
        return
    att.status = "abandoned" if abandoned else "finished"
    att.result, att.upgrade_grade, att.suggested_grade = decide(att.declared_grade, theta, se)
    _update_template_stats(db, att, theta)
    cand.theta, cand.theta_se = theta, se
    if att.result in ("confirmed", "confirmed_plus") and cand.grade != att.declared_grade:
        prev = cand.grade
        lower_after_fail = db.execute(
            select(func.count(TestAttempt.id)).where(TestAttempt.candidate_id == cand.id,
                                                    TestAttempt.result == "not_confirmed",
                                                    TestAttempt.id != att.id)).scalar()
        reason = "lower_test" if lower_after_fail and (prev is None or grade_index(att.declared_grade) < grade_index(prev)) else "test"
        cand.grade = att.declared_grade
        cand.grade_changed_at = att.finished_at
        db.add(GradeEvent(candidate_id=cand.id, from_grade=prev, to_grade=att.declared_grade, reason=reason,
                          attempt_id=att.id, created_at=att.finished_at))
    db.flush()
    _recompute_verified_topics(db, cand)


def accept_upgrade(db: Session, cand: CandidateProfile, att: TestAttempt) -> None:
    if att.candidate_id != cand.id:
        raise HTTPException(404, "Попытка не найдена")
    if att.result != "confirmed_plus" or att.upgrade_accepted or not att.upgrade_grade:
        raise HTTPException(409, "Повышение по этой попытке недоступно")
    if utcnow() - att.finished_at > timedelta(days=settings.upgrade_accept_window_days):
        raise HTTPException(409, "Срок принятия повышения истёк")
    if cand.grade != att.declared_grade:
        raise HTTPException(409, "Грейд уже изменился после этой попытки")
    prev = cand.grade
    cand.grade = att.upgrade_grade
    att.upgrade_accepted = True
    # Повышение — часть результата той же попытки, отдельной сменой грейда не считается
    cand.grade_changed_at = att.finished_at
    db.add(GradeEvent(candidate_id=cand.id, from_grade=prev, to_grade=att.upgrade_grade, reason="upgrade", attempt_id=att.id))
    db.commit()


# ---------------------------------------------------------------- представление для API


def item_public(item: TestItem) -> dict:
    p = item.payload
    return {
        "id": item.id,
        "order": item.order,
        "stem": p["stem"],
        "code": p.get("code"),
        "code_lang": p.get("code_lang"),
        "options": p["options"],
        "time_limit_sec": settings.item_time_limit_sec,
        "served_at": item.served_at.isoformat() + "Z",
        "topic_labels": [skill_label(t) for t in REGISTRY[item.template_id].topics] if item.template_id in REGISTRY else [],
    }


def attempt_public(att: TestAttempt) -> dict:
    answered = [it for it in att.items if it.answered_at is not None]
    cur = current_item(att) if att.status == "in_progress" else None
    out = {
        "id": att.id,
        "specialization": att.specialization,
        "declared_grade": att.declared_grade,
        "status": att.status,
        "answered": len(answered),
        "min_items": settings.test_min_items,
        "max_items": settings.test_max_items,
        "started_at": att.started_at.isoformat() + "Z",
        "finished_at": att.finished_at.isoformat() + "Z" if att.finished_at else None,
        "current_item": item_public(cur) if cur else None,
    }
    if att.status != "in_progress":
        topics: dict[str, dict] = {}
        for it in answered:
            t = REGISTRY.get(it.template_id)
            p = float(irt.p_correct(att.theta, t.a, t.b)) if t and att.theta is not None else 0.5
            for topic in (t.topics if t else []):
                rec = topics.setdefault(topic, {"topic": topic, "label": skill_label(topic), "correct": 0, "total": 0, "expected": 0.0})
                rec["total"] += 1
                rec["correct"] += int(bool(it.is_correct))
                rec["expected"] += p
        for rec in topics.values():
            rec["expected"] = round(rec["expected"], 2)
            rec["status"] = "verified" if topic_verified(rec) else "refuted" if topic_refuted(rec) else "neutral"
        out.update({
            "theta": att.theta, "se": att.se, "n_items": att.n_items, "result": att.result,
            "upgrade_grade": att.upgrade_grade, "suggested_grade": att.suggested_grade,
            "upgrade_accepted": att.upgrade_accepted,
            "correct": sum(1 for it in answered if it.is_correct),
            "timed_out": sum(1 for it in answered if it.timed_out),
            "topics": sorted(topics.values(), key=lambda r: -r["total"]),
            "trace": [{"order": it.order, "is_correct": bool(it.is_correct), "theta": it.theta_after, "se": it.se_after,
                       "b": REGISTRY[it.template_id].b if it.template_id in REGISTRY else None} for it in answered],
        })
    return out


# ---------------------------------------------------------------- план заданий под вакансию


def blueprint(spec: str, grade: str, stack: list[str], n_samples: int = 2) -> dict:
    """Как система сформирует тест под вакансию: какие шаблоны и темы получат приоритет и с какой сложностью.

    Работодатель не пишет задания вручную: из стека и грейда вакансии берутся шаблоны банка, темы которых
    пересекаются со стеком, с наибольшей информативностью около порога нужного грейда. Примеры экземпляров
    генерируются с разными зёрнами, чтобы было видно: у каждого кандидата задание своё.
    """
    cut = grade_cutoff(grade)
    stack_set = set(stack)
    pool = templates_for_spec(spec)
    scored = []
    for t in pool:
        relevant = bool(set(t.topics) & stack_set)
        w = irt.fisher_info(cut, t.a, t.b) * (1.5 if relevant else 1.0)
        scored.append((w, relevant, t))
    scored.sort(key=lambda x: x[0], reverse=True)
    plan = []
    for w, relevant, t in scored[:12]:
        delta = t.b - cut
        plan.append({
            "template_id": t.id, "title": t.title, "pool": t.pool, "fmt": t.fmt,
            "topics": [{"code": x, "label": skill_label(x)} for x in t.topics],
            "relevant": relevant, "a": t.a, "b": t.b,
            "difficulty": "около порога" if abs(delta) < 0.5 else ("выше порога" if delta > 0 else "ниже порога"),
            "info": round(w, 3), "variants": t.variants,
        })
    covered = sorted({x for t in pool for x in t.topics} & stack_set)
    uncovered = sorted(stack_set - set(covered))
    rng = random.Random(f"{spec}:{grade}:{','.join(sorted(stack))}")
    sample_templates = [p for p in plan if p["relevant"]][:n_samples] or plan[:n_samples]
    samples = []
    for p in sample_templates:
        t = REGISTRY[p["template_id"]]
        a_seed, b_seed = rng.randrange(2**31), rng.randrange(2**31)
        samples.append({"template_id": t.id, "title": t.title,
                        "instances": [t.generate(a_seed).public_payload(), t.generate(b_seed).public_payload()]})
    return {
        "specialization": spec, "grade": grade, "cutoff": cut,
        "plan": plan,
        "covered_topics": [{"code": x, "label": skill_label(x)} for x in covered],
        "uncovered_topics": [{"code": x, "label": skill_label(x)} for x in uncovered],
        "samples": samples,
        "rules": {"min_items": settings.test_min_items, "max_items": settings.test_max_items,
                  "time_limit_sec": settings.item_time_limit_sec, "core_share_max": CORE_SHARE_MAX},
    }
