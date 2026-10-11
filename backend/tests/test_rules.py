"""Ключевые правила ТЗ и spec.md: регистрация, видимость контактов, обязательная вилка, роли, тестирование."""
from app.db import SessionLocal
from app.models import TestItem
from app.services import irt
from app.services.bank import REGISTRY
from app.services.testing import decide, stop_rule


def pass_test(client, h, grade, correct=True):
    att = client.post("/api/tests/start", headers=h, json={"declared_grade": grade}).json()
    while att["status"] == "in_progress":
        it = att["current_item"]
        assert "correct_index" not in it and "explanation" not in str(it)  # ответ не покидает сервер
        db = SessionLocal()
        ci = db.get(TestItem, it["id"]).correct_index
        db.close()
        att = client.post(f"/api/tests/{att['id']}/answer", headers=h,
                          json={"item_id": it["id"], "answer_index": ci if correct else (ci + 1) % len(it["options"])}).json()
    return att


def make_candidate(client, register, email, grade="middle"):
    h = register(email)
    client.put("/api/candidate/profile", headers=h, json={"full_name": "Иванов Иван", "phone": "+79990001122"})
    r = client.post("/api/candidate/survey", headers=h, json={
        "specialization": "backend", "stack": ["python", "sql", "postgresql", "docker"], "experience_years": 3,
        "work_format": ["remote"], "salary_expect_min": 250000})
    assert r.status_code == 200, r.text
    att = pass_test(client, h, grade)
    assert att["result"] in ("confirmed", "confirmed_plus")
    client.put("/api/candidate/privacy", headers=h, json={"consent_publish": True, "job_status": "active"})
    return h


def make_employer(client, register, email):
    h = register(email, "employer")
    assert client.get("/api/employer/needs", headers=h).status_code == 409  # без профиля компании подбор недоступен
    assert client.put("/api/employer/company", headers=h, json={"name": f"Компания {email}"}).status_code == 200
    return h


def test_registration_requires_consent_and_verified_email(client):
    r = client.post("/api/auth/register", json={"email": "noconsent@t.ru", "password": "password1", "role": "candidate", "consent_pd": False})
    assert r.status_code == 422
    r = client.post("/api/auth/register", json={"email": "unverified@t.ru", "password": "password1", "role": "candidate", "consent_pd": True})
    assert r.status_code == 201
    assert client.post("/api/auth/login", json={"email": "unverified@t.ru", "password": "password1"}).status_code == 403


def test_roles_are_separated(client, register):
    hc = register("role.c@t.ru")
    he = register("role.e@t.ru", "employer")
    assert client.get("/api/employer/dashboard", headers=hc).status_code == 403
    assert client.get("/api/candidate/profile", headers=he).status_code == 403
    assert client.get("/api/candidate/profile").status_code == 401


def test_contacts_hidden_until_accept_and_salary_required(client, register):
    hc = make_candidate(client, register, "contacts.c@t.ru")
    he = make_employer(client, register, "contacts.e@t.ru")
    cid = client.get("/api/candidate/profile", headers=hc).json()["id"]
    card = client.get(f"/api/employer/candidates/{cid}", headers=he).json()
    assert card["contacts"] is None and "Иванов" not in card["display_name"]
    base = {"candidate_id": cid, "title": "Python dev", "description": "Приглашаем в команду платежей", "contact_method": "tg @hr"}
    assert client.post("/api/employer/invitations", headers=he, json=base).status_code == 422  # нет вилки
    assert client.post("/api/employer/invitations", headers=he, json={**base, "salary_from": 300000, "salary_to": 200000}).status_code == 422
    inv = client.post("/api/employer/invitations", headers=he, json={**base, "salary_from": 200000, "salary_to": 300000})
    assert inv.status_code == 201
    assert client.post("/api/employer/invitations", headers=he, json={**base, "salary_from": 200000, "salary_to": 300000}).status_code == 409
    mine = client.get("/api/candidate/invitations", headers=hc).json()
    assert mine[0]["salary_from"] == 200000 and mine[0]["company"]["name"]
    assert client.post(f"/api/candidate/invitations/{mine[0]['id']}/accept", headers=hc).json()["status"] == "accepted"
    card = client.get(f"/api/employer/candidates/{cid}", headers=he).json()
    assert card["contacts"]["phone"] == "+79990001122"


def test_hidden_from_company_and_publish_consent(client, register):
    hc = make_candidate(client, register, "hidden.c@t.ru")
    he = make_employer(client, register, "hidden.e@t.ru")
    cid = client.get("/api/candidate/profile", headers=hc).json()["id"]
    assert client.get(f"/api/employer/candidates/{cid}", headers=he).status_code == 200
    client.put("/api/candidate/privacy", headers=hc, json={"consent_publish": True, "hidden_companies": ["Компания hidden.e@t.ru"]})
    assert client.get(f"/api/employer/candidates/{cid}", headers=he).status_code == 404
    client.put("/api/candidate/privacy", headers=hc, json={"consent_publish": False})
    bank = client.get("/api/employer/candidates", headers=he, params={"specialization": "backend"}).json()
    assert cid not in [x["id"] for x in bank["items"]]


def test_grade_change_cooldown_and_no_forced_downgrade(client, register):
    h = register("cooldown@t.ru")
    client.put("/api/candidate/profile", headers=h, json={"full_name": "Петров Пётр"})
    client.post("/api/candidate/survey", headers=h, json={"specialization": "qa", "stack": ["test_design", "sql"],
                                                          "experience_years": 1, "work_format": ["remote"], "salary_expect_min": 90000})
    fail = pass_test(client, h, "senior", correct=False)
    assert fail["result"] == "not_confirmed" and fail["suggested_grade"]
    r = client.post("/api/tests/start", headers=h, json={"declared_grade": "senior"})
    assert r.status_code == 409 and r.json()["detail"]["available_at"]  # повтор того же грейда — через 30 дней
    ok = pass_test(client, h, "junior")  # грейд ниже — сразу
    assert ok["result"] in ("confirmed", "confirmed_plus")
    r = client.post("/api/tests/start", headers=h, json={"declared_grade": "middle"})
    assert r.status_code == 409  # смена подтверждённого грейда — не чаще раза в 90 дней


def test_decide_rules():
    assert decide("middle", 0.9, 0.3)[0] == "confirmed"
    assert decide("middle", 2.2, 0.3) == ("confirmed_plus", "senior", None)
    res, up, sugg = decide("senior", 0.6, 0.3)
    assert res == "not_confirmed" and sugg == "middle" and up is None
    assert decide("senior", 3.0, 0.2)[0] == "confirmed"  # выше senior повышать некуда


def test_stop_rule_and_eap():
    assert not stop_rule("middle", 3.0, 0.2, 5)  # не раньше минимума вопросов
    assert stop_rule("middle", 0.4, 0.9, 20)  # максимум вопросов
    th_hi, _ = irt.eap([(1.2, 0.0, 1)] * 6)
    th_lo, _ = irt.eap([(1.2, 0.0, 0)] * 6)
    assert th_hi > 0.5 > -0.5 > th_lo


def test_parametric_instances_differ():
    t = next(iter(REGISTRY.values()))
    a, b = t.generate(1), t.generate(2)
    assert (a.stem, a.code, a.options) != (b.stem, b.code, b.options)
    assert t.generate(1).options == a.options  # детерминированность по зерну
