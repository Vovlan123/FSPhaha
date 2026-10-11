"""Сериализация сущностей для API и общие операции, нужные обоим кабинетам."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.dictionaries import DECLINE_REASONS, STATUS_LABELS, category_label, skill_label
from app.models import Application, CandidateProfile, Company, Invitation, RegularTask, TaskAssignment, Vacancy, utcnow

_DECLINE = {d["code"]: d["label"] for d in DECLINE_REASONS}


def iso(dt: datetime | None) -> str | None:
    return dt.isoformat() + "Z" if dt else None


def expire_invitations(db: Session) -> None:
    """Ленивое истечение срока приглашений: без фоновых задач, при каждом чтении списков."""
    db.execute(update(Invitation).where(Invitation.status.in_(["sent", "viewed"]), Invitation.expires_at < utcnow())
               .values(status="expired"))
    db.commit()


def company_public(c: Company) -> dict:
    return {"id": c.id, "name": c.name, "industry": c.industry, "city": c.city, "website": c.website,
            "description": c.description, "size": c.size}


def invitation_out(inv: Invitation, side: str) -> dict:
    out = {
        "id": inv.id, "title": inv.title, "description": inv.description,
        "salary_from": inv.salary_from, "salary_to": inv.salary_to, "work_format": inv.work_format,
        "contact_method": inv.contact_method, "status": inv.status,
        "status_label": STATUS_LABELS["invitation"].get(inv.status, inv.status),
        # Работодатель видит пометку только если кандидат не скрыл ожидания: иначе она раскрывала бы их косвенно
        "below_expectations": inv.below_expectations and (side == "candidate" or (inv.candidate.privacy or {}).get("show_salary", True)),
        "decline_reason": inv.decline_reason, "decline_reason_label": _DECLINE.get(inv.decline_reason or ""),
        "decline_comment": inv.decline_comment, "expected_salary": inv.expected_salary,
        "complaint_reason": inv.complaint_reason, "complaint_comment": inv.complaint_comment,
        "complaint_at": iso(inv.complaint_at), "company_verified": inv.company.verified,
        "created_at": iso(inv.created_at), "viewed_at": iso(inv.viewed_at), "responded_at": iso(inv.responded_at),
        "expires_at": iso(inv.expires_at), "need_id": inv.need_id, "vacancy_id": inv.vacancy_id,
        "company": company_public(inv.company),
    }
    if side == "employer":
        c: CandidateProfile = inv.candidate
        accepted = inv.status == "accepted"
        out["candidate"] = {
            "id": c.id, "anon_code": c.anon_code, "category": category_label(c.specialization, c.grade),
            "display_name": c.full_name if accepted and c.full_name else f"Кандидат {c.anon_code}",
            "contacts": {"full_name": c.full_name, "email": c.contact_email or c.user.email, "phone": c.phone,
                         "telegram": c.telegram} if accepted else None,
        }
    return out


def vacancy_out(v: Vacancy) -> dict:
    return {
        "id": v.id, "title": v.title, "description": v.description, "specialization": v.specialization, "grade": v.grade,
        "category": category_label(v.specialization, v.grade),
        "stack": v.stack, "stack_labels": [skill_label(s) for s in v.stack or []],
        "work_format": v.work_format, "city": v.city, "salary_from": v.salary_from, "salary_to": v.salary_to,
        "status": v.status, "created_at": iso(v.created_at), "updated_at": iso(v.updated_at),
        "company": company_public(v.company),
    }


def application_out(a: Application, side: str) -> dict:
    out = {
        "id": a.id, "status": a.status, "status_label": STATUS_LABELS["application"].get(a.status, a.status),
        "cover_letter": a.cover_letter, "match_score": a.match_score,
        "created_at": iso(a.created_at), "updated_at": iso(a.updated_at), "vacancy": vacancy_out(a.vacancy),
    }
    if side == "employer":
        c = a.candidate
        # Кандидат откликнулся сам — контакты видны этой компании (ТЗ, п. 2.2)
        out["candidate"] = {"id": c.id, "anon_code": c.anon_code, "display_name": c.full_name or f"Кандидат {c.anon_code}",
                            "category": category_label(c.specialization, c.grade),
                            "contacts": {"full_name": c.full_name, "email": c.contact_email or c.user.email,
                                         "phone": c.phone, "telegram": c.telegram}}
    return out


def task_out(t: RegularTask) -> dict:
    return {"id": t.id, "title": t.title, "body": t.body, "kind": t.kind, "specialization": t.specialization,
            "grades": t.grades, "rubric": t.rubric, "active": t.active, "created_at": iso(t.created_at),
            "company": company_public(t.company)}


def assignment_out(a: TaskAssignment, side: str) -> dict:
    out = {"id": a.id, "status": a.status, "status_label": STATUS_LABELS["assignment"].get(a.status, a.status),
           "answer": a.answer, "auto_score": a.auto_score, "rubric_hits": a.rubric_hits,
           "employer_score": a.employer_score, "assigned_at": iso(a.assigned_at), "submitted_at": iso(a.submitted_at)}
    if side == "candidate":
        t = a.task
        out["task"] = {"id": t.id, "title": t.title, "body": t.body, "kind": t.kind, "company": t.company.name,
                       "rubric_points": [p["point"] for p in t.rubric]}
    else:
        c = a.candidate
        out["candidate"] = {"id": c.id, "anon_code": c.anon_code, "category": category_label(c.specialization, c.grade)}
    return out


def candidate_new_invitations(db: Session, cand_id: int) -> int:
    return len(db.execute(select(Invitation.id).where(Invitation.candidate_id == cand_id, Invitation.status == "sent")).all())
