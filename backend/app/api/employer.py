from datetime import timedelta

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.common import (application_out, assignment_out, expire_invitations, invitation_out, iso, task_out,
                            vacancy_out)
from app.config import settings
from app.db import get_db
from app.dictionaries import SPEC_BY_CODE, category_label, skill_label
from app.emailer import send_email
from app.models import (Application, CandidateProfile, Company, Invitation, Need, RegularTask, SelectionItem,
                        TaskAssignment, User, Vacancy, WebhookDelivery, utcnow)
from app.schemas import (ERRORS, AppStatusIn, CompanyIn, InvitationIn, NeedIn, ParseIn, RateIn, TaskIn, VacancyIn,
                         WebhookIn)
from app.security import current_company, current_employer_user
from app.services import matching, nlp, pdf, testing, trust, webhooks

router = APIRouter(prefix="/employer", tags=["Кабинет работодателя"], responses=ERRORS)


# ---------------------------------------------------------------- компания и дашборд


def company_out(c: Company) -> dict:
    return {"id": c.id, "name": c.name, "description": c.description, "industry": c.industry, "website": c.website,
            "city": c.city, "size": c.size, "contact_email": c.contact_email, "contact_telegram": c.contact_telegram,
            "contact_phone": c.contact_phone, "invite_quota_week": c.invite_quota_week, "complete": bool(c.name.strip()),
            "inn": c.inn, "verified": c.verified, "verified_at": iso(c.verified_at),
            "verification_checks": trust.verification_checks(c),
            "webhook_url": c.webhook_url, "webhook_secret": c.webhook_secret}


@router.get("/company", summary="Профиль компании")
def get_company(user: User = Depends(current_employer_user), db: Session = Depends(get_db)):
    c = db.execute(select(Company).where(Company.user_id == user.id)).scalar_one()
    return company_out(c)


@router.put("/company", summary="Заполнить или изменить профиль компании")
def put_company(body: CompanyIn, user: User = Depends(current_employer_user), db: Session = Depends(get_db)):
    c = db.execute(select(Company).where(Company.user_id == user.id)).scalar_one()
    before = (c.inn, c.website, c.contact_email)
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    if c.verified and before != (c.inn, c.website, c.contact_email):
        c.verified, c.verified_at = False, None  # изменились проверенные данные — подтверждение заново
    db.commit()
    return company_out(c)


@router.post("/company/verify", summary="Подтвердить компанию: ИНН (контрольная сумма) + корпоративный домен")
def verify_company(user: User = Depends(current_employer_user), db: Session = Depends(get_db)):
    c = db.execute(select(Company).where(Company.user_id == user.id)).scalar_one()
    ok, checks = trust.verify(c)
    db.commit()
    return {**company_out(c), "verification_ok": ok}


def quota(db: Session, company: Company) -> dict:
    return trust.weekly_quota(db, company)


@router.get("/dashboard", summary="Сводка: сетка категорий, приглашения по статусам, квота")
def dashboard(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    expire_invitations(db)
    by_status = dict(db.execute(select(Invitation.status, func.count(Invitation.id)).where(Invitation.company_id == company.id)
                                .group_by(Invitation.status)).all())
    new_apps = db.execute(select(func.count(Application.id)).join(Vacancy).where(Vacancy.company_id == company.id,
                                                                              Application.status == "sent")).scalar()
    needs = db.execute(select(func.count(Need.id)).where(Need.company_id == company.id)).scalar()
    return {"company": company_out(company), "categories": matching.categories_grid(db, company),
            "invitations": by_status, "quota": quota(db, company), "new_applications": new_apps, "needs": needs}


@router.get("/categories", summary="Сетка категорий «специализация × грейд» с числом кандидатов")
def categories(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    return matching.categories_grid(db, company)


# ---------------------------------------------------------------- банк кандидатов


@router.get("/candidates", summary="Поиск по банку кандидатов (только категоризированные и согласившиеся на публикацию)")
def search_candidates(specialization: str | None = None, grade: str | None = None,
                      stack: str | None = Query(None, description="Навыки через запятую, все должны быть в профиле"),
                      has_fsp: bool = False, verified_only: bool = Query(False, description="Навыки из stack подтверждены тестом"),
                      q: str | None = None, sort: str = Query("strength", pattern="^(strength|theta|fsp|salary)$"),
                      limit: int = Query(30, ge=1, le=100), offset: int = Query(0, ge=0),
                      company: Company = Depends(current_company), db: Session = Depends(get_db)):
    pool = matching.visible_candidates(db, company, specialization)
    if grade:
        pool = [c for c in pool if c.grade == grade]
    need_stack = [s.strip() for s in (stack or "").split(",") if s.strip()]
    if need_stack:
        if verified_only:
            pool = [c for c in pool if all(matching.is_verified(c, s) for s in need_stack)]
        else:
            pool = [c for c in pool if all(s in (c.stack or []) or matching.is_verified(c, s) for s in need_stack)]
    asg = matching.assignments_by_candidate(db, [c.id for c in pool])
    rows = [(c, matching.strength(c, asg.get(c.id, []))) for c in pool]
    if has_fsp:
        rows = [(c, st) for c, st in rows if st.fsp_items]
    if q:
        ql = q.lower()
        rows = [(c, st) for c, st in rows if ql in (c.about or "").lower() or ql in c.anon_code.lower()
                or any(ql in skill_label(s).lower() for s in c.stack or [])]
    key = {"strength": lambda x: -x[1].P, "theta": lambda x: -(x[0].theta or -9), "fsp": lambda x: -x[1].F,
           "salary": lambda x: x[0].salary_expect_min or 10**9}[sort]
    rows.sort(key=key)
    inv = _last_invitations(db, company, [c.id for c, _ in rows[offset:offset + limit]])
    return {"total": len(rows), "items": [{**matching.candidate_summary(c, st), "invitation": inv.get(c.id)}
                                          for c, st in rows[offset:offset + limit]]}


def _last_invitations(db: Session, company: Company, ids: list[int]) -> dict[int, dict]:
    if not ids:
        return {}
    out: dict[int, dict] = {}
    for inv in db.execute(select(Invitation).where(Invitation.company_id == company.id, Invitation.candidate_id.in_(ids))
                          .order_by(Invitation.created_at)).scalars():
        out[inv.candidate_id] = {"id": inv.id, "status": inv.status}
    return out


def _visible_candidate(db: Session, company: Company, cid: int) -> CandidateProfile:
    cand = db.get(CandidateProfile, cid)
    if cand is None:
        raise HTTPException(404, "Кандидат не найден")
    visible = any(c.id == cid for c in matching.visible_candidates(db, company, cand.specialization))
    # Кандидат, который принял приглашение или откликнулся, остаётся доступен этой компании даже вне выдачи
    if not visible and not matching.contacts_unlocked(db, company.id, cid):
        raise HTTPException(404, "Кандидат не найден или скрыл профиль")
    return cand


@router.get("/candidates/{cid}", summary="Карточка кандидата (анонимна до принятия приглашения или отклика)")
def candidate_card(cid: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    return matching.candidate_card(db, _visible_candidate(db, company, cid), company)


@router.get("/candidates/{cid}/profile.pdf", summary="PDF-профиль кандидата (анонимный до раскрытия контактов)",
            response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
def candidate_pdf(cid: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    cand = _visible_candidate(db, company, cid)
    card = matching.candidate_card(db, cand, company)
    data = pdf.profile_pdf(cand, card["strength"], card["fsp"], card["tasks"], anonymized=not card["contacts_unlocked"])
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="candidate-{cand.id}.pdf"'})


# ---------------------------------------------------------------- потребности и подборка


def need_out(n: Need, db: Session | None = None) -> dict:
    out = {"id": n.id, "title": n.title, "description": n.description, "team_about": n.team_about,
           "specialization": n.specialization, "grade": n.grade, "category": category_label(n.specialization, n.grade),
           "stack_must": n.stack_must, "stack_nice": n.stack_nice, "work_format": n.work_format, "city": n.city,
           "salary_from": n.salary_from, "salary_to": n.salary_to, "selection_at": iso(n.selection_at),
           "created_at": iso(n.created_at), "updated_at": iso(n.updated_at)}
    if db is not None:
        out["selection_size"] = db.execute(select(func.count(SelectionItem.id)).where(SelectionItem.need_id == n.id)).scalar()
        out["pinned"] = db.execute(select(func.count(SelectionItem.id)).where(SelectionItem.need_id == n.id,
                                                                            SelectionItem.pinned.is_(True))).scalar()
    return out


def _own_need(db: Session, company: Company, need_id: int) -> Need:
    n = db.get(Need, need_id)
    if n is None or n.company_id != company.id:
        raise HTTPException(404, "Потребность не найдена")
    return n


@router.post("/needs/parse", summary="Разобрать текст описания потребности в структуру (NLP)")
def parse_need(body: ParseIn, company: Company = Depends(current_company)):
    r = nlp.parse_need(body.text)
    r["stack_must_labels"] = [skill_label(s) for s in r["stack_must"]]
    r["stack_nice_labels"] = [skill_label(s) for s in r["stack_nice"]]
    if r["specialization"]:
        allowed = set(SPEC_BY_CODE[r["specialization"]]["skills"])
        r["outside_specialization"] = [s for s in r["stack_must"] + r["stack_nice"] if s not in allowed]
    return r


@router.get("/needs", summary="Мои потребности")
def list_needs(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    rows = db.execute(select(Need).where(Need.company_id == company.id).order_by(Need.updated_at.desc())).scalars()
    return [need_out(n, db) for n in rows]


@router.post("/needs", status_code=201, summary="Создать потребность и сразу сформировать подборку")
def create_need(body: NeedIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = Need(company_id=company.id, **body.model_dump())
    db.add(n)
    db.commit()
    matching.build_selection(db, n, company)
    return need_out(n, db)


@router.get("/needs/{need_id}", summary="Потребность")
def get_need(need_id: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    return need_out(_own_need(db, company, need_id), db)


@router.put("/needs/{need_id}", summary="Уточнить потребность (подборка пересчитывается, шорт-лист сохраняется)")
def update_need(need_id: int, body: NeedIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _own_need(db, company, need_id)
    for k, v in body.model_dump().items():
        setattr(n, k, v)
    db.commit()
    matching.build_selection(db, n, company)
    return need_out(n, db)


@router.delete("/needs/{need_id}", status_code=204, summary="Удалить потребность")
def delete_need(need_id: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _own_need(db, company, need_id)
    for si in db.execute(select(SelectionItem).where(SelectionItem.need_id == n.id)).scalars():
        db.delete(si)
    for inv in db.execute(select(Invitation).where(Invitation.need_id == n.id)).scalars():
        inv.need_id = None
    db.delete(n)
    db.commit()
    return Response(status_code=204)


@router.post("/needs/{need_id}/selection", summary="Пересчитать подборку (шорт-лист сохраняется, новые помечаются)")
def rebuild_selection(need_id: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _own_need(db, company, need_id)
    matching.build_selection(db, n, company)
    # Обработчик вызывается напрямую, поэтому все параметры фильтров передаются явно (иначе останутся объекты Query)
    return get_selection(need_id, stack=None, has_fsp=False, confident_only=False, salary_fit=False, pinned_only=False,
                         new_only=False, min_score=0, company=company, db=db)


@router.get("/needs/{need_id}/selection", summary="Подборка с фильтрами поверх сохранённого результата")
def get_selection(need_id: int, stack: str | None = Query(None, description="Навыки через запятую"),
                  has_fsp: bool = False, confident_only: bool = Query(False, description="T ≥ 0.5: уверенно в грейде"),
                  salary_fit: bool = Query(False, description="Ожидания не выше вилки"), pinned_only: bool = False,
                  new_only: bool = False, min_score: float = 0,
                  company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _own_need(db, company, need_id)
    if n.selection_at is None:
        matching.build_selection(db, n, company)
    items = db.execute(select(SelectionItem).where(SelectionItem.need_id == n.id).order_by(SelectionItem.rank)).scalars().all()
    total = len(items)
    cands = {c.id: c for c in db.execute(select(CandidateProfile).where(
        CandidateProfile.id.in_([i.candidate_id for i in items]))).scalars()}
    asg = matching.assignments_by_candidate(db, list(cands))
    want_stack = [s.strip() for s in (stack or "").split(",") if s.strip()]
    inv = _last_invitations(db, company, list(cands))
    out = []
    for si in items:
        c = cands.get(si.candidate_id)
        if c is None:
            continue
        st = matching.strength(c, asg.get(c.id, []))
        if pinned_only and not si.pinned:
            continue
        if new_only and not si.is_new:
            continue
        if si.score < min_score:
            continue
        if has_fsp and not st.fsp_items:
            continue
        if confident_only and st.T < 0.5:
            continue
        if salary_fit and c.salary_expect_min and (c.privacy or {}).get("show_salary", True) and c.salary_expect_min > n.salary_to:
            continue
        if want_stack and not all(s in (c.stack or []) or matching.is_verified(c, s) for s in want_stack):
            continue
        out.append({**matching.candidate_summary(c, st), "score": si.score, "components": si.components,
                    "reasons": si.reasons, "pinned": si.pinned, "is_new": si.is_new, "rank": si.rank,
                    "invitation": inv.get(c.id)})
    spec = matching.NeedSpec.from_need(n)
    return {"need": need_out(n, db), "categories": matching.recommended_categories(db, spec, company),
            "total": total, "shown": len(out), "items": out}


@router.post("/needs/{need_id}/selection/{cid}/pin", summary="Добавить в шорт-лист или убрать из него")
def pin(need_id: int, cid: int, pinned: bool = Body(True, embed=True),
        company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _own_need(db, company, need_id)
    si = db.execute(select(SelectionItem).where(SelectionItem.need_id == n.id, SelectionItem.candidate_id == cid)).scalar_one_or_none()
    if si is None:
        raise HTTPException(404, "Кандидата нет в подборке")
    si.pinned = pinned
    db.commit()
    return {"candidate_id": cid, "pinned": si.pinned}


@router.get("/needs/{need_id}/blueprint", summary="Какие задания система сформирует под эту потребность")
def need_blueprint(need_id: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    n = _own_need(db, company, need_id)
    return testing.blueprint(n.specialization, n.grade, list(n.stack_must or []) + list(n.stack_nice or []))


# ---------------------------------------------------------------- приглашения


@router.get("/invitations/quota", summary="Недельная квота приглашений")
def get_quota(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    return quota(db, company)


@router.post("/invitations", status_code=201, summary="Пригласить кандидата: вилка обязательна",
             responses={429: {"description": "Исчерпана недельная квота приглашений"}})
def create_invitation(body: InvitationIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    expire_invitations(db)
    cand = _visible_candidate(db, company, body.candidate_id)
    q = quota(db, company)
    if q["left"] <= 0:
        raise HTTPException(429, q["reason"] or f"Исчерпана недельная квота приглашений ({q['limit']}). "
                                               "Квота заставляет выбирать, а не рассылать всем подряд")
    active = db.execute(select(Invitation.id).where(Invitation.company_id == company.id, Invitation.candidate_id == cand.id,
                                                    Invitation.status.in_(["sent", "viewed"]))).first()
    if active:
        raise HTTPException(409, "У этого кандидата уже есть активное приглашение от вашей компании")
    if body.need_id is not None:
        _own_need(db, company, body.need_id)
    if body.vacancy_id is not None:
        v = db.get(Vacancy, body.vacancy_id)
        if v is None or v.company_id != company.id:
            raise HTTPException(404, "Вакансия не найдена")
    inv = Invitation(company_id=company.id, candidate_id=cand.id, need_id=body.need_id, vacancy_id=body.vacancy_id,
                     title=body.title, description=body.description, salary_from=body.salary_from,
                     salary_to=body.salary_to, work_format=body.work_format, contact_method=body.contact_method,
                     below_expectations=bool(cand.salary_expect_min and body.salary_to < cand.salary_expect_min),
                     expires_at=utcnow() + timedelta(days=settings.invite_ttl_days))
    db.add(inv)
    db.commit()
    send_email(cand.contact_email or cand.user.email, f"Новое приглашение от {company.name}",
               f"{company.name} приглашает вас на позицию «{inv.title}».\n"
               f"Зарплата: {inv.salary_from:,} – {inv.salary_to:,} ₽/мес.\n"
               f"Ответить можно в кабинете: {settings.frontend_url}/candidate/invitations".replace(",", " "))
    return invitation_out(inv, "employer")


@router.get("/invitations", summary="Мои приглашения и их статусы")
def list_invitations(status: str | None = None, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    expire_invitations(db)
    q = select(Invitation).where(Invitation.company_id == company.id)
    if status:
        q = q.where(Invitation.status == status)
    return [invitation_out(i, "employer") for i in db.execute(q.order_by(Invitation.created_at.desc())).scalars()]


@router.post("/invitations/{inv_id}/withdraw", summary="Отозвать приглашение до ответа кандидата")
def withdraw(inv_id: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    inv = db.get(Invitation, inv_id)
    if inv is None or inv.company_id != company.id:
        raise HTTPException(404, "Приглашение не найдено")
    if inv.status not in ("sent", "viewed"):
        raise HTTPException(409, "Отозвать можно только приглашение без ответа")
    inv.status = "withdrawn"
    db.commit()
    return invitation_out(inv, "employer")


# ---------------------------------------------------------------- вакансии и отклики


def _own_vacancy(db: Session, company: Company, vid: int) -> Vacancy:
    v = db.get(Vacancy, vid)
    if v is None or v.company_id != company.id:
        raise HTTPException(404, "Вакансия не найдена")
    return v


@router.get("/vacancies", summary="Мои вакансии")
def list_vacancies(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    rows = db.execute(select(Vacancy).where(Vacancy.company_id == company.id).order_by(Vacancy.updated_at.desc())).scalars().all()
    counts = dict(db.execute(select(Application.vacancy_id, func.count(Application.id))
                             .where(Application.vacancy_id.in_([v.id for v in rows])).group_by(Application.vacancy_id)).all())
    new = dict(db.execute(select(Application.vacancy_id, func.count(Application.id))
                          .where(Application.vacancy_id.in_([v.id for v in rows]), Application.status == "sent")
                          .group_by(Application.vacancy_id)).all())
    return [{**vacancy_out(v), "applications": counts.get(v.id, 0), "new_applications": new.get(v.id, 0)} for v in rows]


@router.post("/vacancies", status_code=201, summary="Опубликовать вакансию (вилка обязательна)")
def create_vacancy(body: VacancyIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = Vacancy(company_id=company.id, **body.model_dump())
    db.add(v)
    db.commit()
    return vacancy_out(v)


@router.put("/vacancies/{vid}", summary="Редактировать вакансию или снять с публикации")
def update_vacancy(vid: int, body: VacancyIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = _own_vacancy(db, company, vid)
    for k, val in body.model_dump().items():
        setattr(v, k, val)
    db.commit()
    return vacancy_out(v)


@router.get("/vacancies/{vid}/applications", summary="Отклики на вакансию (открытие помечает их просмотренными)")
def vacancy_applications(vid: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    v = _own_vacancy(db, company, vid)
    rows = db.execute(select(Application).where(Application.vacancy_id == v.id).order_by(Application.match_score.desc())).scalars().all()
    for a in rows:
        if a.status == "sent":
            a.status = "viewed"
    db.commit()
    return [application_out(a, "employer") for a in rows]


@router.post("/applications/{app_id}/status", summary="Изменить статус отклика")
def application_status(app_id: int, body: AppStatusIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    a = db.get(Application, app_id)
    if a is None or a.vacancy.company_id != company.id:
        raise HTTPException(404, "Отклик не найден")
    a.status = body.status
    db.commit()
    return application_out(a, "employer")


# ---------------------------------------------------------------- регулярные задания


@router.get("/tasks", summary="Мои регулярные задания со статистикой решений")
def list_tasks(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    rows = db.execute(select(RegularTask).where(RegularTask.company_id == company.id).order_by(RegularTask.created_at.desc())).scalars().all()
    out = []
    for t in rows:
        subs = db.execute(select(TaskAssignment).where(TaskAssignment.task_id == t.id)).scalars().all()
        done = [s for s in subs if s.status == "submitted"]
        out.append({**task_out(t), "assigned": len(subs), "submitted": len(done),
                    "avg_auto_score": round(sum(s.auto_score or 0 for s in done) / len(done), 3) if done else None})
    return out


@router.post("/tasks", status_code=201, summary="Создать регулярное задание с рубрикой оценки")
def create_task(body: TaskIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    data = body.model_dump()
    t = RegularTask(company_id=company.id, **data)
    db.add(t)
    db.commit()
    return task_out(t)


@router.post("/tasks/{tid}/active", summary="Включить или выключить выдачу задания")
def toggle_task(tid: int, active: bool = Body(..., embed=True), company: Company = Depends(current_company),
                db: Session = Depends(get_db)):
    t = db.get(RegularTask, tid)
    if t is None or t.company_id != company.id:
        raise HTTPException(404, "Задание не найдено")
    t.active = active
    db.commit()
    return task_out(t)


@router.get("/tasks/{tid}/submissions", summary="Решения кандидатов (анонимно)")
def task_submissions(tid: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    t = db.get(RegularTask, tid)
    if t is None or t.company_id != company.id:
        raise HTTPException(404, "Задание не найдено")
    rows = db.execute(select(TaskAssignment).where(TaskAssignment.task_id == t.id, TaskAssignment.status == "submitted")
                      .order_by(TaskAssignment.auto_score.desc())).scalars()
    rows = list(rows)
    inv = _last_invitations(db, company, [a.candidate_id for a in rows])
    out = [{**assignment_out(a, "employer"), "invitation": inv.get(a.candidate_id)} for a in rows]
    return {"task": task_out(t), "submissions": out}


@router.post("/submissions/{aid}/rate", summary="Оценить решение (1–5)")
def rate(aid: int, body: RateIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    a = db.get(TaskAssignment, aid)
    if a is None or a.task.company_id != company.id:
        raise HTTPException(404, "Решение не найдено")
    if a.status != "submitted":
        raise HTTPException(409, "Решение ещё не отправлено")
    a.employer_score = body.score
    db.commit()
    return assignment_out(a, "employer")


@router.get("/candidates/{cid}/export.json", summary="Экспорт кандидата для импорта в ATS (после раскрытия контактов)",
            tags=["Интеграция с ATS"])
def export_candidate(cid: int, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    cand = _visible_candidate(db, company, cid)
    card = matching.candidate_card(db, cand, company)
    if not card["contacts_unlocked"]:
        raise HTTPException(403, "Экспорт доступен после того, как кандидат принял приглашение или откликнулся")
    return webhooks.candidate_export(cand, card)


# ---------------------------------------------------------------- интеграция с ATS (вебхуки)


def integration_out(db: Session, company: Company) -> dict:
    rows = db.execute(select(WebhookDelivery).where(WebhookDelivery.company_id == company.id)
                      .order_by(WebhookDelivery.created_at.desc()).limit(30)).scalars().all()
    return {"webhook_url": company.webhook_url, "webhook_secret": company.webhook_secret, "events": webhooks.EVENTS,
            "signature_header": "X-FSP-Signature: sha256=HMAC_SHA256(secret, body)",
            "deliveries": [{"id": d.id, "event": d.event, "status": d.status, "response_code": d.response_code,
                            "error": d.error, "attempts": d.attempts, "created_at": iso(d.created_at),
                            "delivered_at": iso(d.delivered_at)} for d in rows]}


@router.get("/integrations", summary="Настройки вебхуков и журнал доставок", tags=["Интеграция с ATS"])
def get_integrations(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    return integration_out(db, company)


@router.put("/integrations/webhook", summary="Задать URL приёмника событий в ATS", tags=["Интеграция с ATS"])
def set_webhook(body: WebhookIn, company: Company = Depends(current_company), db: Session = Depends(get_db)):
    company.webhook_url = body.url
    if body.url and not company.webhook_secret:
        company.webhook_secret = webhooks.new_secret()
    db.commit()
    return integration_out(db, company)


@router.post("/integrations/webhook/rotate", summary="Выпустить новый секрет подписи", tags=["Интеграция с ATS"])
def rotate_secret(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    company.webhook_secret = webhooks.new_secret()
    db.commit()
    return integration_out(db, company)


@router.post("/integrations/webhook/test", summary="Отправить тестовое событие ping", tags=["Интеграция с ATS"])
def test_webhook(company: Company = Depends(current_company), db: Session = Depends(get_db)):
    if not company.webhook_url:
        raise HTTPException(409, "Сначала укажите URL приёмника")
    webhooks.emit(db, company, "ping", {"message": "Тестовое событие ФСП Талант", "company": company.name})
    return integration_out(db, company)

