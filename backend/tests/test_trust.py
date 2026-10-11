"""Защита от недобросовестных работодателей и интеграция с ATS."""
import hashlib
import hmac
import time

from app.services.trust import inn_valid, make_inn
from app.services.webhooks import sign
from tests.test_rules import make_candidate, make_employer


def test_inn_checksum():
    assert inn_valid("7707083893")          # действующий ИНН юрлица (ПАО Сбербанк, публичные данные)
    assert not inn_valid("7707083894")      # ошибка в контрольной цифре
    assert inn_valid("500100732259")        # 12-значный ИНН с верными контрольными цифрами
    assert not inn_valid("12345")
    assert inn_valid(make_inn("770123456"))


def test_unverified_company_has_lower_quota_and_verification(client, register):
    he = make_employer(client, register, "trust.e@t.ru")
    q = client.get("/api/employer/invitations/quota", headers=he).json()
    assert q["limit"] == 5 and not q["verified"] and q["reason"]
    r = client.post("/api/employer/company/verify", headers=he).json()
    assert r["verification_ok"] is False and any(not c["ok"] for c in r["verification_checks"])
    client.put("/api/employer/company", headers=he, json={"name": "Компания trust.e@t.ru", "inn": make_inn("770987654"),
                                                           "website": "https://acme.example", "contact_email": "hr@acme.example"})
    assert client.post("/api/employer/company/verify", headers=he).json()["verification_ok"] is True
    assert client.get("/api/employer/invitations/quota", headers=he).json()["limit"] == 20
    client.put("/api/employer/company", headers=he, json={"name": "Компания trust.e@t.ru", "inn": make_inn("770987654"),
                                                           "website": "https://acme.example", "contact_email": "acme@gmail.com"})
    assert client.get("/api/employer/company", headers=he).json()["verified"] is False  # данные изменились — подтверждение снято


def test_complaint_closes_invitation_without_contacts(client, register):
    hc = make_candidate(client, register, "complain.c@t.ru")
    he = make_employer(client, register, "complain.e@t.ru")
    cid = client.get("/api/candidate/profile", headers=hc).json()["id"]
    client.post("/api/employer/invitations", headers=he, json={"candidate_id": cid, "title": "Странная вакансия",
                "description": "Заработок без опыта, пишите в личку", "contact_method": "tg @x",
                "salary_from": 10000, "salary_to": 20000})
    inv = client.get("/api/candidate/invitations", headers=hc).json()[0]
    assert "Компания не подтвердила ИНН и корпоративный домен" in inv["trust"]["warnings"]
    r = client.post(f"/api/candidate/invitations/{inv['id']}/complain", headers=hc, json={"reason": "fake"}).json()
    assert r["status"] == "declined" and r["complaint_reason"] == "fake"
    assert client.post(f"/api/candidate/invitations/{inv['id']}/complain", headers=hc, json={"reason": "fake"}).status_code == 409
    assert client.get(f"/api/employer/candidates/{cid}", headers=he).json()["contacts"] is None
    assert client.get(f"/api/employer/candidates/{cid}/export.json", headers=he).status_code == 403


def test_webhook_signature_and_delivery(client, register):
    he = make_employer(client, register, "hook.e@t.ru")
    r = client.put("/api/employer/integrations/webhook", headers=he, json={"url": "ftp://bad"})
    assert r.status_code == 422
    r = client.put("/api/employer/integrations/webhook", headers=he, json={"url": "http://127.0.0.1:9/nowhere"}).json()
    assert len(r["webhook_secret"]) == 48
    client.post("/api/employer/integrations/webhook/test", headers=he)
    time.sleep(0.5)
    d = client.get("/api/employer/integrations", headers=he).json()["deliveries"][0]
    assert d["event"] == "ping" and d["status"] in ("pending", "failed")  # приёмник недоступен — попытки и ошибка в журнале
    body = b'{"event":"ping"}'
    assert sign("s3cr3t", body) == "sha256=" + hmac.new(b"s3cr3t", body, hashlib.sha256).hexdigest()
