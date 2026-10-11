from datetime import timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import application_out, assignment_out, candidate_new_invitations, expire_invitations, invitation_out, iso
from app.config import settings
from app.db import get_db
from app.dictionaries import GRADE_BY_CODE, category_label, skill_label
from app.emailer import send_email
from app.models import Application, CandidateProfile, GradeEvent, Invitation, SurveyResponse, TaskAssignment, TestAttempt, utcnow
from app.schemas import ERRORS, ComplaintIn, DeclineIn, PrivacyIn, ProfileIn, SubmitIn, SurveyIn
from app.security import current_candidate
from app.services import matching, nlp, pdf, tasks, testing, trust, webhooks

router = APIRouter(prefix="/candidate", tags=["Кабинет кандидата"], responses=ERRORS)


def profile_out(c: CandidateProfile) -> dict:
    return {
        "id": c.id, "anon_code": c.anon_code, "email": c.user.email,
        "full_name": c.full_name, "phone": c.phone, "telegram": c.telegram, "contact_email": c.contact_email,
        "city": c.city, "relocation": c.relocation, "about": c.about, "experience_years": c.experience_years,
        "roles": c.roles, "soft_skills": c.soft_skills, "industries": c.industries,
        "specialization": c.specialization, "stack": c.stack, "work_format": c.work_format,
        "salary_expect_min": c.salary_expect_min, "grade": c.grade, "theta": c.theta, "theta_se": c.theta_se,
        "category": category_label(c.specialization, c.grade), "grade_changed_at": iso(c.grade_changed_at),
        "job_status": c.job_status, "consent_publish": c.consent_publish_at is not None,
        "consent_publish_at": iso(c.consent_publish_at), "consent_pd_at": iso(c.user.consent_pd_at),
        "privacy": c.privacy, "resume_source": c.resume_source,
        "fsp": matching.fsp_public(c, for_employer=False),
    }


@router.get("/profile", summary="Мой профиль")
def get_profile(cand: CandidateProfile = Depends(current_candidate)):
    return profile_out(cand)


@router.put("/profile", summary="Заполнить или изменить профиль (форма или подтверждённые данные из PDF)")
def put_profile(body: ProfileIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    for k, v in body.model_dump().items():
        setattr(cand, k, v)
    db.commit()
    return profile_out(cand)


@router.post("/resume/parse", summary="Распознать PDF-резюме (поля возвращаются для проверки, не сохраняются)")
async def parse_resume(file: UploadFile = File(...), cand: CandidateProfile = Depends(current_candidate)):
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(422, "Файл больше 5 МБ")
    if not data.startswith(b"%PDF"):
        raise HTTPException(422, "Загрузите файл в формате PDF")
    try:
        text = pdf.extract_text(data)
    except Exception:  # noqa: BLE001 — повреждённый PDF
        raise HTTPException(422, "Не удалось прочитать PDF, заполните форму вручную") from None
    if len(text.strip()) < 30:
        raise HTTPException(422, "Не удалось извлечь текст (возможно, это скан). Заполните форму вручную")
    parsed = nlp.parse_resume(text)
    parsed["stack_labels"] = [skill_label(s) for s in parsed["stack"]]
    parsed["chars"] = len(text)
    return parsed


@router.post("/survey", summary="Опрос: отрасль, специализация, стек, условия, предполагаемый грейд")
def survey(body: SurveyIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    if cand.grade and cand.specialization and body.specialization != cand.specialization:
        until = (cand.grade_changed_at or utcnow()) + timedelta(days=settings.grade_change_cooldown_days)
        if until > utcnow():
            raise HTTPException(409, {"message": "Сменить специализацию можно после окончания периода смены грейда",
                                      "available_at": iso(until)})
        # Новая специализация — новая категория: грейд нужно подтвердить заново
        cand.grade, cand.theta, cand.theta_se, cand.verified_topics = None, None, None, {}
    if testing.active_attempt(db, cand) is not None:
        raise HTTPException(409, "Завершите текущий тест перед изменением опроса")
    data = body.model_dump()
    db.add(SurveyResponse(candidate_id=cand.id, answers=data))
    for k in ("industries", "specialization", "stack", "experience_years", "work_format", "salary_expect_min", "city", "relocation"):
        setattr(cand, k, data[k])
    db.commit()
    return profile_out(cand)


@router.get("/status", summary="Сводка: категория, сила профиля, доступность тестов, следующие шаги")
def status(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    asg = db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)).scalars().all()
    st = matching.strength(cand, list(asg), for_employer=False)
    att = testing.active_attempt(db, cand)
    db.commit()
    avail = testing.availability(db, cand)
    steps = {
        "profile": bool(cand.full_name.strip()),
        "survey": bool(cand.specialization and cand.stack),
        "test": cand.grade is not None,
        "publish": cand.consent_publish_at is not None,
        "fsp": bool(cand.fsp_id),
    }
    return {
        "steps": steps,
        "onboarding_complete": steps["profile"] and steps["survey"] and steps["test"],
        "category": category_label(cand.specialization, cand.grade),
        "specialization": cand.specialization, "grade": cand.grade,
        "grade_label": GRADE_BY_CODE[cand.grade]["label"] if cand.grade else None,
        "theta": cand.theta, "theta_se": cand.theta_se, "grade_changed_at": iso(cand.grade_changed_at),
        "next_grade_change_at": iso(cand.grade_changed_at + timedelta(days=settings.grade_change_cooldown_days)) if cand.grade_changed_at else None,
        "strength": st.as_dict(),
        "visible_to_employers": bool(cand.grade and cand.consent_publish_at and cand.job_status != "closed"),
        "job_status": cand.job_status,
        "active_attempt_id": att.id if att else None,
        "availability": [{"grade": a.grade, "allowed": a.allowed, "reason": a.reason, "available_at": iso(a.available_at)} for a in avail],
        "new_invitations": candidate_new_invitations(db, cand.id),
        "verified_skills": [{"code": s, "label": skill_label(s)} for s in matching.verified_skills(cand)],
        "fsp": matching.fsp_public(cand, for_employer=False),
        "next_task_at": iso(tasks.next_task_available_at(db, cand)),
    }


@router.get("/history", summary="История опросов, попыток теста и изменений грейда")
def history(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    surveys = db.execute(select(SurveyResponse).where(SurveyResponse.candidate_id == cand.id)
                         .order_by(SurveyResponse.created_at.desc())).scalars().all()
    attempts = db.execute(select(TestAttempt).where(TestAttempt.candidate_id == cand.id)
                          .order_by(TestAttempt.started_at.desc())).scalars().all()
    events = db.execute(select(GradeEvent).where(GradeEvent.candidate_id == cand.id)
                        .order_by(GradeEvent.created_at.desc())).scalars().all()
    return {
        "surveys": [{"id": s.id, "created_at": iso(s.created_at), "answers": s.answers} for s in surveys],
        "attempts": [{k: v for k, v in testing.attempt_public(a).items() if k not in ("current_item", "trace")} for a in attempts],
        "grade_events": [{"from_grade": e.from_grade, "to_grade": e.to_grade, "reason": e.reason,
                          "attempt_id": e.attempt_id, "created_at": iso(e.created_at)} for e in events],
    }


@router.put("/privacy", summary="Приватность, согласие на публикацию, статус поиска")
def privacy(body: PrivacyIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    data = body.model_dump()
    cand.privacy = {k: data[k] for k in ("show_name", "show_salary", "show_fsp", "show_tasks", "hidden_companies")}
    cand.job_status = body.job_status
    if body.consent_publish and cand.consent_publish_at is None:
        cand.consent_publish_at = utcnow()
    elif not body.consent_publish:
        cand.consent_publish_at = None  # отзыв согласия — профиль сразу пропадает из выдачи
    db.commit()
    return profile_out(cand)


@router.get("/profile.pdf", summary="Стандартизированный PDF-профиль", response_class=Response,
            responses={200: {"content": {"application/pdf": {}}}})
def profile_pdf(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    asg = db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)).scalars().all()
    st = matching.strength(cand, list(asg), for_employer=False)
    done = [{"title": a.task.title, "auto_score": a.auto_score, "employer_score": a.employer_score} for a in asg if a.status == "submitted"]
    data = pdf.profile_pdf(cand, st.as_dict(), matching.fsp_public(cand, False), done, anonymized=False)
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="profile-{cand.id}.pdf"'})


# ---------------------------------------------------------------- приглашения


@router.get("/invitations", summary="Мои приглашения")
def my_invitations(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    expire_invitations(db)
    rows = db.execute(select(Invitation).where(Invitation.candidate_id == cand.id).order_by(Invitation.created_at.desc())).scalars()
    return [{**invitation_out(i, "candidate"), "trust": trust.signals_for_candidate(db, i)} for i in rows]


def candidate_invitation(db: Session, inv: Invitation) -> dict:
    return {**invitation_out(inv, "candidate"), "trust": trust.signals_for_candidate(db, inv)}


def _event_data(inv: Invitation, cand: CandidateProfile) -> dict:
    data = {"invitation_id": inv.id, "title": inv.title, "status": inv.status,
            "salary_from": inv.salary_from, "salary_to": inv.salary_to,
            "candidate": {"anon_code": cand.anon_code, "category": category_label(cand.specialization, cand.grade)}}
    if inv.status == "accepted":  # контакты раскрыты — передаём их в ATS
        data["candidate"].update({"full_name": cand.full_name, "email": cand.contact_email or cand.user.email,
                                  "phone": cand.phone, "telegram": cand.telegram})
    if inv.status == "declined":
        data.update({"decline_reason": inv.decline_reason, "expected_salary": inv.expected_salary})
    return data


def _own_invitation(db: Session, cand: CandidateProfile, inv_id: int) -> Invitation:
    inv = db.get(Invitation, inv_id)
    if inv is None or inv.candidate_id != cand.id:
        raise HTTPException(404, "Приглашение не найдено")
    return inv


@router.get("/invitations/{inv_id}", summary="Открыть приглашение (статус «просмотрено»)")
def open_invitation(inv_id: int, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    expire_invitations(db)
    inv = _own_invitation(db, cand, inv_id)
    if inv.status == "sent":
        inv.status, inv.viewed_at = "viewed", utcnow()
        db.commit()
    return candidate_invitation(db, inv)


@router.post("/invitations/{inv_id}/accept", summary="Принять приглашение — контакты раскрываются работодателю")
def accept_invitation(inv_id: int, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    expire_invitations(db)
    inv = _own_invitation(db, cand, inv_id)
    if inv.status not in ("sent", "viewed"):
        raise HTTPException(409, f"Приглашение в статусе «{inv.status}», ответить нельзя")
    inv.status, inv.responded_at = "accepted", utcnow()
    inv.viewed_at = inv.viewed_at or inv.responded_at
    db.commit()
    send_email(inv.company.contact_email or inv.company.user.email, f"Кандидат {cand.anon_code} принял приглашение",
               f"Кандидат принял приглашение «{inv.title}». Контакты доступны в кабинете работодателя.")
    webhooks.emit(db, inv.company, "invitation.accepted", _event_data(inv, cand))
    return candidate_invitation(db, inv)


@router.post("/invitations/{inv_id}/decline", summary="Отклонить приглашение с причиной")
def decline_invitation(inv_id: int, body: DeclineIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    expire_invitations(db)
    inv = _own_invitation(db, cand, inv_id)
    if inv.status not in ("sent", "viewed"):
        raise HTTPException(409, f"Приглашение в статусе «{inv.status}», ответить нельзя")
    inv.status, inv.responded_at = "declined", utcnow()
    inv.viewed_at = inv.viewed_at or inv.responded_at
    inv.decline_reason, inv.decline_comment = body.reason, body.comment
    inv.expected_salary = body.expected_salary if body.reason == "salary" else None
    db.commit()
    webhooks.emit(db, inv.company, "invitation.declined", _event_data(inv, cand))
    return candidate_invitation(db, inv)


@router.post("/invitations/{inv_id}/complain", summary="Пожаловаться на приглашение (фиктивная вакансия, спам, обман)")
def complain(inv_id: int, body: ComplaintIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    inv = _own_invitation(db, cand, inv_id)
    if inv.complaint_at:
        raise HTTPException(409, "Жалоба на это приглашение уже отправлена")
    inv.complaint_reason, inv.complaint_comment, inv.complaint_at = body.reason, body.comment, utcnow()
    if inv.status in ("sent", "viewed"):  # жалоба закрывает приглашение без раскрытия контактов
        inv.status, inv.responded_at, inv.decline_reason = "declined", utcnow(), "other"
        inv.viewed_at = inv.viewed_at or inv.responded_at
    db.commit()
    return candidate_invitation(db, inv)


# ---------------------------------------------------------------- отклики и задания


@router.get("/applications", summary="Мои отклики на вакансии")
def my_applications(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    rows = db.execute(select(Application).where(Application.candidate_id == cand.id).order_by(Application.created_at.desc())).scalars()
    return [application_out(a, "candidate") for a in rows]


@router.get("/tasks", summary="Текущее регулярное задание и история")
def my_tasks(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    rows = db.execute(select(TaskAssignment).where(TaskAssignment.candidate_id == cand.id)
                      .order_by(TaskAssignment.assigned_at.desc())).scalars().all()
    current = next((a for a in rows if a.status == "assigned"), None)
    return {"current": assignment_out(current, "candidate") if current else None,
            "history": [assignment_out(a, "candidate") for a in rows if a.status != "assigned"],
            "next_task_at": iso(tasks.next_task_available_at(db, cand)),
            "interval_days": settings.task_interval_days}


@router.post("/tasks/next", summary="Получить новое задание (не чаще раза в TASK_INTERVAL_DAYS)")
def next_task(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    if cand.grade is None:
        raise HTTPException(409, "Регулярные задания доступны после подтверждения грейда")
    a = tasks.assign_next(db, cand)
    if a is None:
        at = tasks.next_task_available_at(db, cand)
        raise HTTPException(409, {"message": "Новых заданий пока нет" if at is None else "Следующее задание будет доступно позже",
                                  "available_at": iso(at)})
    return assignment_out(a, "candidate")


def _own_assignment(db: Session, cand: CandidateProfile, aid: int) -> TaskAssignment:
    a = db.get(TaskAssignment, aid)
    if a is None or a.candidate_id != cand.id:
        raise HTTPException(404, "Задание не найдено")
    if a.status != "assigned":
        raise HTTPException(409, "Ответ на это задание уже принят")
    return a


@router.post("/tasks/{aid}/submit", summary="Отправить решение или подход")
def submit_task(aid: int, body: SubmitIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = _own_assignment(db, cand, aid)
    a.answer = body.answer
    a.auto_score, a.rubric_hits = tasks.score_answer(body.answer, a.task.rubric)
    a.status, a.submitted_at = "submitted", utcnow()
    db.commit()
    webhooks.emit(db, a.task.company, "task.submitted", {
        "task_id": a.task.id, "task_title": a.task.title, "assignment_id": a.id, "auto_score": a.auto_score,
        "candidate": {"anon_code": cand.anon_code, "category": category_label(cand.specialization, cand.grade)}})
    return assignment_out(a, "candidate")


@router.post("/tasks/{aid}/skip", summary="Пропустить задание")
def skip_task(aid: int, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    a = _own_assignment(db, cand, aid)
    a.status = "skipped"
    db.commit()
    return assignment_out(a, "candidate")
