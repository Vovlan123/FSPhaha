"""Регулярные короткие задания от работодателей: выдача кандидатам и автооценка ответа по рубрике.

Рубрика — список ключевых пунктов, каждый со списком ключевых слов/основ. Пункт засчитан, если в ответе
встречается хотя бы одно ключевое слово. Это прозрачная и объяснимая предварительная оценка; итоговую
оценку 1–5 ставит работодатель. В продуктиве автооценку можно заменить LLM-оценщиком с той же рубрикой.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import CandidateProfile, RegularTask, TaskAssignment, utcnow
from app.services.nlp import tokens


def score_answer(answer: str, rubric: list[dict]) -> tuple[float, list[str]]:
    if not rubric:
        return 0.0, []
    toks = set(tokens(answer))
    low = answer.lower()
    hits = []
    for point in rubric:
        for kw in point.get("keywords", []):
            kw_l = kw.lower().strip()
            if not kw_l:
                continue
            kw_toks = tokens(kw_l)
            if kw_l in low or (kw_toks and all(t in toks for t in kw_toks)):
                hits.append(point["point"])
                break
    score = len(hits) / len(rubric)
    if len(answer.strip()) < 40:  # отписка из пары слов не должна набирать высокий балл
        score *= 0.5
    return round(score, 3), hits


def next_task_available_at(db: Session, cand: CandidateProfile):
    last = db.execute(select(TaskAssignment.assigned_at).where(TaskAssignment.candidate_id == cand.id)
                      .order_by(TaskAssignment.assigned_at.desc())).scalars().first()
    if last is None:
        return None
    at = last + timedelta(days=settings.task_interval_days)
    return at if at > utcnow() else None


def assign_next(db: Session, cand: CandidateProfile) -> TaskAssignment | None:
    """Выдаёт кандидату новое задание его специализации и грейда, которое он ещё не получал.
    Не чаще одного раза в TASK_INTERVAL_DAYS и не больше одного активного задания одновременно."""
    active = db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id,
                                                     TaskAssignment.status == "assigned")).scalars().first()
    if active:
        return active
    if next_task_available_at(db, cand) is not None or not cand.specialization:
        return None
    got = set(db.execute(select(TaskAssignment.task_id).where(TaskAssignment.candidate_id == cand.id)).scalars())
    tasks = db.execute(select(RegularTask).where(RegularTask.active.is_(True), RegularTask.specialization == cand.specialization)
                       .order_by(RegularTask.created_at.desc())).scalars().all()
    for t in tasks:
        if t.id in got:
            continue
        if t.grades and cand.grade and cand.grade not in t.grades:
            continue
        a = TaskAssignment(task_id=t.id, candidate_id=cand.id, status="assigned")
        db.add(a)
        db.commit()
        return a
    return None
