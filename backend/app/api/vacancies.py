from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import application_out, vacancy_out
from app.db import get_db
from app.models import Application, CandidateProfile, TaskAssignment, User, Vacancy
from app.schemas import ERRORS, ApplyIn
from app.security import current_candidate, current_user
from app.dictionaries import category_label
from app.services import matching, testing, webhooks

router = APIRouter(prefix="/vacancies", tags=["Вакансии (кандидат)"], responses=ERRORS)


def _match(cand: CandidateProfile, v: Vacancy, asg: list[TaskAssignment]) -> dict | None:
    if cand.grade is None:
        return None
    st = matching.strength(cand, asg, for_employer=False)
    return matching.match(matching.NeedSpec.from_vacancy(v), cand, st)


@router.get("", summary="Опубликованные вакансии с процентом соответствия моему профилю")
def list_vacancies(specialization: str | None = None, grade: str | None = None, q: str | None = None,
                   cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    query = select(Vacancy).where(Vacancy.status == "published")
    if specialization:
        query = query.where(Vacancy.specialization == specialization)
    if grade:
        query = query.where(Vacancy.grade == grade)
    rows = db.execute(query.order_by(Vacancy.created_at.desc())).scalars().all()
    if q:
        ql = q.lower()
        rows = [v for v in rows if ql in v.title.lower() or ql in v.description.lower() or ql in v.company.name.lower()]
    applied = {a.vacancy_id: a for a in db.execute(select(Application).where(Application.candidate_id == cand.id)).scalars()}
    asg = list(db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)).scalars())
    out = []
    for v in rows:
        m = _match(cand, v, asg)
        a = applied.get(v.id)
        out.append({**vacancy_out(v), "match": {"score": m["score"], "reasons": m["reasons"][:4]} if m else None,
                    "application": {"id": a.id, "status": a.status} if a else None})
    # Сначала подходящие по специализации кандидата, затем по баллу соответствия
    out.sort(key=lambda x: (x["specialization"] != cand.specialization, -(x["match"]["score"] if x["match"] else 0)))
    return out


@router.get("/{vid}", summary="Вакансия")
def get_vacancy(vid: int, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    v = db.get(Vacancy, vid)
    if v is None or v.status != "published":
        raise HTTPException(404, "Вакансия не найдена")
    asg = list(db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)).scalars())
    a = db.execute(select(Application).where(Application.vacancy_id == vid, Application.candidate_id == cand.id)).scalar_one_or_none()
    return {**vacancy_out(v), "match": _match(cand, v, asg), "application": {"id": a.id, "status": a.status} if a else None}


@router.post("/{vid}/apply", status_code=201, summary="Откликнуться: контакты станут видны этой компании")
def apply(vid: int, body: ApplyIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    v = db.get(Vacancy, vid)
    if v is None or v.status != "published":
        raise HTTPException(404, "Вакансия не найдена")
    if not cand.full_name.strip():
        raise HTTPException(409, "Заполните профиль перед откликом")
    if db.execute(select(Application.id).where(Application.vacancy_id == vid, Application.candidate_id == cand.id)).first():
        raise HTTPException(409, "Вы уже откликались на эту вакансию")
    asg = list(db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)).scalars())
    m = _match(cand, v, asg)
    a = Application(vacancy_id=v.id, candidate_id=cand.id, cover_letter=body.cover_letter, match_score=m["score"] if m else None)
    db.add(a)
    db.commit()
    webhooks.emit(db, v.company, "application.created", {
        "application_id": a.id, "vacancy_id": v.id, "vacancy_title": v.title, "match_score": a.match_score,
        "cover_letter": a.cover_letter,
        "candidate": {"anon_code": cand.anon_code, "category": category_label(cand.specialization, cand.grade),
                      "full_name": cand.full_name, "email": cand.contact_email or cand.user.email,
                      "phone": cand.phone, "telegram": cand.telegram}})
    return application_out(a, "candidate")


@router.get("/{vid}/blueprint", summary="Какие задания система сформирует под эту вакансию", tags=["Тестирование"])
def vacancy_blueprint(vid: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    v = db.get(Vacancy, vid)
    if v is None:
        raise HTTPException(404, "Вакансия не найдена")
    if v.status != "published" and not (user.role == "employer" and v.company.user_id == user.id):
        raise HTTPException(404, "Вакансия не найдена")
    return testing.blueprint(v.specialization, v.grade, list(v.stack or []))
