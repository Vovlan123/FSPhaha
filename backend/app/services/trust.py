"""Защита от фиктивных вакансий и недобросовестных работодателей.

Что реализовано в MVP (концепция целиком — docs/documentation.md, раздел 9.1):
  * верификация компании: ИНН с проверкой контрольной суммы + корпоративный email на домене сайта компании.
    В продуктиве ИНН сверяется с ЕГРЮЛ ФНС, а на корпоративный адрес отправляется код подтверждения;
  * неподтверждённой компании — пониженная недельная квота приглашений;
  * сигналы доверия для кандидата прямо в приглашении: подтверждена ли компания, как кандидаты отвечают
    на её приглашения, жалобы, массовая рассылка одного текста, вилка заметно ниже рынка категории;
  * жалобы кандидатов: при достижении порога приглашения компании приостанавливаются до проверки модератором.
"""
from __future__ import annotations

import re
import statistics
from datetime import timedelta
from urllib.parse import urlparse

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.dictionaries import COMPLAINT_CODES, COMPLAINT_REASONS  # noqa: F401 — реэкспорт для API
from app.models import CandidateProfile, Company, Invitation, utcnow

FREE_MAIL = {"gmail.com", "mail.ru", "yandex.ru", "ya.ru", "bk.ru", "inbox.ru", "list.ru", "rambler.ru",
             "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "proton.me", "protonmail.com"}
MASS_MAILING_MIN = 10       # столько одинаковых текстов за 7 дней — «массовая рассылка»
BELOW_MARKET_RATIO = 0.7    # верх вилки ниже 70% медианы ожиданий категории — «заметно ниже рынка»


def inn_valid(inn: str) -> bool:
    """Проверка контрольных цифр ИНН (10 цифр — юрлицо, 12 — ИП/физлицо) по алгоритму ФНС."""
    if not re.fullmatch(r"\d{10}|\d{12}", inn or ""):
        return False
    d = [int(c) for c in inn]

    def check(coefs: list[int], n: int) -> int:
        return sum(c * x for c, x in zip(coefs, d[:n])) % 11 % 10

    if len(d) == 10:
        return check([2, 4, 10, 3, 5, 9, 4, 6, 8], 9) == d[9]
    return (check([7, 2, 4, 10, 3, 5, 9, 4, 6, 8], 10) == d[10]
            and check([3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8], 11) == d[11])


def make_inn(seed_digits: str) -> str:
    """Достраивает 9 цифр до валидного 10-значного ИНН (для демо-данных)."""
    d = [int(c) for c in seed_digits[:9]]
    n10 = sum(c * x for c, x in zip([2, 4, 10, 3, 5, 9, 4, 6, 8], d)) % 11 % 10
    return seed_digits[:9] + str(n10)


def _domain(value: str) -> str:
    value = (value or "").strip().lower()
    if "@" in value:
        return value.rsplit("@", 1)[1]
    host = urlparse(value if "://" in value else f"https://{value}").hostname or ""
    return host.removeprefix("www.")


def verification_checks(company: Company) -> list[dict]:
    """Список проверок с результатом — показывается работодателю, чтобы было понятно, чего не хватает."""
    site, mail = _domain(company.website), _domain(company.contact_email)
    return [
        {"code": "inn", "ok": inn_valid(company.inn),
         "text": "ИНН указан и проходит проверку контрольной суммы" if inn_valid(company.inn)
         else "Укажите ИНН компании (10 цифр для юрлица, 12 — для ИП)"},
        {"code": "site", "ok": bool(site), "text": f"Сайт компании: {site}" if site else "Укажите сайт компании"},
        {"code": "domain", "ok": bool(mail) and mail not in FREE_MAIL and bool(site) and (mail == site or mail.endswith("." + site)),
         "text": "Контактный email на домене сайта компании" if mail and site and mail not in FREE_MAIL and (mail == site or mail.endswith("." + site))
         else "Контактный email должен быть на домене сайта (не gmail, mail.ru и т. п.)"},
    ]


def verify(company: Company) -> tuple[bool, list[dict]]:
    checks = verification_checks(company)
    ok = all(c["ok"] for c in checks)
    company.verified = ok
    company.verified_at = utcnow() if ok else None
    return ok, checks


def stats(db: Session, company_id: int) -> dict:
    """Как кандидаты отвечают на приглашения компании за 90 дней + жалобы."""
    since = utcnow() - timedelta(days=90)
    rows = dict(db.execute(select(Invitation.status, func.count(Invitation.id))
                           .where(Invitation.company_id == company_id, Invitation.created_at >= since)
                           .group_by(Invitation.status)).all())
    complaints = db.execute(select(func.count(Invitation.id)).where(Invitation.company_id == company_id,
                                                                   Invitation.complaint_at.is_not(None))).scalar() or 0
    total = sum(rows.values())
    answered = rows.get("accepted", 0) + rows.get("declined", 0)
    return {"invitations_90d": total, "accepted": rows.get("accepted", 0), "declined": rows.get("declined", 0),
            "accept_rate": round(rows.get("accepted", 0) / answered, 2) if answered else None,
            "complaints": complaints, "suspended": complaints >= settings.complaints_to_suspend}


def weekly_quota(db: Session, company: Company) -> dict:
    since = utcnow() - timedelta(days=7)
    used = db.execute(select(func.count(Invitation.id)).where(Invitation.company_id == company.id,
                                                             Invitation.created_at >= since)).scalar() or 0
    st = stats(db, company.id)
    if st["suspended"]:
        limit, reason = 0, f"Приглашения приостановлены: {st['complaints']} жалоб кандидатов, нужна проверка модератора"
    elif company.verified:
        limit, reason = company.invite_quota_week, None
    else:
        limit, reason = min(company.invite_quota_week, settings.invite_quota_unverified), \
            "Компания не подтверждена — квота снижена. Подтвердите компанию в профиле"
    return {"limit": limit, "used": used, "left": max(limit - used, 0), "verified": company.verified,
            "reason": reason, "full_limit": company.invite_quota_week}


def mass_mailing_count(db: Session, inv: Invitation) -> int:
    since = inv.created_at - timedelta(days=7)
    return db.execute(select(func.count(Invitation.id)).where(Invitation.company_id == inv.company_id,
                                                             Invitation.description == inv.description,
                                                             Invitation.created_at >= since)).scalar() or 0


def category_median(db: Session, cand: CandidateProfile) -> int | None:
    vals = db.execute(select(CandidateProfile.salary_expect_min).where(
        CandidateProfile.specialization == cand.specialization, CandidateProfile.grade == cand.grade,
        CandidateProfile.salary_expect_min.is_not(None))).scalars().all()
    return int(statistics.median(vals)) if len(vals) >= 5 else None


def signals_for_candidate(db: Session, inv: Invitation) -> dict:
    """Сигналы доверия, которые кандидат видит в карточке приглашения."""
    st = stats(db, inv.company_id)
    mass = mass_mailing_count(db, inv)
    median = category_median(db, inv.candidate)
    below_market = bool(median and inv.salary_to < BELOW_MARKET_RATIO * median)
    warnings = []
    if not inv.company.verified:
        warnings.append("Компания не подтвердила ИНН и корпоративный домен")
    if mass >= MASS_MAILING_MIN:
        warnings.append(f"Этот же текст отправлен {mass} кандидатам за неделю")
    if below_market:
        warnings.append(f"Верх вилки заметно ниже медианы ожиданий вашей категории ({median:,} ₽)".replace(",", " "))
    if st["complaints"]:
        warnings.append(f"На приглашения компании есть жалобы: {st['complaints']}")
    return {"company_verified": inv.company.verified, "accept_rate": st["accept_rate"],
            "invitations_90d": st["invitations_90d"], "complaints": st["complaints"], "mass_mailing": mass,
            "category_median": median, "below_market": below_market, "warnings": warnings}
