"""Интеграция с ATS работодателя: исходящие вебхуки.

Каждое событие подписывается HMAC-SHA256 секретом компании (заголовок `X-FSP-Signature: sha256=<hex>`
от тела запроса), несёт `X-FSP-Event` и `X-FSP-Delivery` (идемпотентный ключ для получателя).
Доставка — в фоновом потоке с тремя попытками и паузой 1 → 3 с; результат пишется в журнал доставок.

События: invitation.accepted, invitation.declined, application.created, task.submitted, ping.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import threading
import time

import httpx
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import Company, WebhookDelivery, utcnow

log = logging.getLogger("fsp_talent.webhooks")
EVENTS = ["invitation.accepted", "invitation.declined", "application.created", "task.submitted"]
RETRY_DELAYS = (1, 3)


def new_secret() -> str:
    return secrets.token_hex(24)


def sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def emit(db: Session, company: Company, event: str, data: dict) -> WebhookDelivery | None:
    """Ставит событие в доставку. Без настроенного URL ничего не делает."""
    if not company.webhook_url:
        return None
    payload = {"event": event, "created_at": utcnow().isoformat() + "Z", "company_id": company.id, "data": data}
    d = WebhookDelivery(company_id=company.id, event=event, url=company.webhook_url, payload=payload)
    db.add(d)
    db.commit()
    threading.Thread(target=_deliver, args=(d.id, company.webhook_secret), daemon=True).start()
    return d


def _deliver(delivery_id: int, secret: str) -> None:
    db = SessionLocal()
    try:
        d = db.get(WebhookDelivery, delivery_id)
        body = json.dumps({**d.payload, "delivery_id": d.id}, ensure_ascii=False).encode()
        headers = {"Content-Type": "application/json", "X-FSP-Event": d.event, "X-FSP-Delivery": str(d.id),
                   "X-FSP-Signature": sign(secret, body), "User-Agent": "FSP-Talent-Webhooks/1.0"}
        for attempt in range(len(RETRY_DELAYS) + 1):
            d.attempts = attempt + 1
            try:
                with httpx.Client(timeout=5, trust_env=False) as http:
                    r = http.post(d.url, content=body, headers=headers)
                d.response_code = r.status_code
                if 200 <= r.status_code < 300:
                    d.status, d.error, d.delivered_at = "delivered", None, utcnow()
                    break
                d.error = f"HTTP {r.status_code}: {r.text[:200]}"
            except httpx.HTTPError as e:
                d.error = f"{type(e).__name__}: {e}"[:300]
            d.status = "failed"
            db.commit()
            if attempt < len(RETRY_DELAYS):
                time.sleep(RETRY_DELAYS[attempt])
        db.commit()
    except Exception:  # noqa: BLE001 — фоновая доставка не должна ронять процесс
        log.exception("Ошибка доставки вебхука %s", delivery_id)
    finally:
        db.close()


def candidate_export(cand, card: dict) -> dict:
    """Кандидат в формате для импорта в ATS (структура близка к HR-Open Standards: person, skills, credentials)."""
    contacts = card.get("contacts") or {}
    return {
        "schema": "fsp-talent/candidate@1",
        "source": {"platform": "ФСП Талант", "candidate_id": cand.anon_code, "exported_at": utcnow().isoformat() + "Z"},
        "person": {"name": contacts.get("full_name"), "email": contacts.get("email"), "phone": contacts.get("phone"),
                   "telegram": contacts.get("telegram"), "city": card.get("city"), "relocation": card.get("relocation")},
        "position": {"category": card.get("category"), "specialization": card.get("specialization"), "grade": card.get("grade"),
                     "grade_confirmed_at": card.get("grade_changed_at"), "theta": card.get("theta"),
                     "theta_se": card.get("theta_se")},
        "skills": [{"name": t["label"], "code": t["topic"], "verified_by_test": t["verified"],
                    "declared": t["topic"] in (card.get("stack") or [])} for t in card.get("verified_topics", [])]
        + [{"name": s, "code": s, "verified_by_test": False, "declared": True}
           for s in card.get("stack", []) if s not in {t["topic"] for t in card.get("verified_topics", [])}],
        "credentials": [{"type": "fsp_achievement", "name": a.get("event_name"), "result": a.get("result_label"),
                         "level": a.get("level_label"), "date": a.get("date"), "team": a.get("team_name")}
                        for a in (card.get("fsp") or {}).get("achievements", [])],
        "experience_years": card.get("experience_years"),
        "salary_expectation_rub": card.get("salary_expect_min"),
        "profile_strength": card.get("strength"),
    }
