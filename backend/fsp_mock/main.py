"""Mock реестра ФСП и ФСП ID с OIDC-эндпоинтами в формате Keycloak.

Пути повторяют Keycloak (/realms/{realm}/protocol/openid-connect/...), поэтому бэкенд платформы работает
с боевым Keycloak ФСП без изменения кода — только конфигурация. API достижений — предложение команды.

Запуск отдельно: uvicorn fsp_mock.main:app --port 8001  (или встроенно в бэкенд под /fsp).
"""
from __future__ import annotations

import html
import os
import secrets
import time
from urllib.parse import urlencode

import jwt
from fastapi import FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from fsp_mock.data import participants

MOCK_SECRET = os.getenv("FSP_MOCK_SECRET", "fsp-mock-signing-key-0123456789abcdef")
CLIENTS = {os.getenv("FSP_CLIENT_ID", "fsp-talent"): os.getenv("FSP_CLIENT_SECRET", "fsp-talent-secret")}
_codes: dict[str, dict] = {}

app = FastAPI(title="ФСП ID (mock)", version="0.1.0",
              description="Эмуляция Keycloak-реалма ФСП и реестра достижений для хакатона.")


def _issue(claims: dict, ttl: int = 600) -> str:
    now = int(time.time())
    return jwt.encode({**claims, "iat": now, "exp": now + ttl, "iss": "fsp-mock"}, MOCK_SECRET, algorithm="HS256")


def _decode(authorization: str | None) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Bearer token required")
    try:
        return jwt.decode(authorization.split(" ", 1)[1], MOCK_SECRET, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid_token") from None


@app.get("/realms/{realm}/.well-known/openid-configuration")
def discovery(realm: str, request: Request):
    base = str(request.url_for("discovery", realm=realm)).removesuffix("/.well-known/openid-configuration")
    oidc = f"{base}/protocol/openid-connect"
    return {"issuer": base, "authorization_endpoint": f"{oidc}/auth", "token_endpoint": f"{oidc}/token",
            "userinfo_endpoint": f"{oidc}/userinfo", "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "client_credentials"],
            "scopes_supported": ["openid", "profile", "fsp_achievements"]}


_PAGE = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ФСП ID — вход</title><style>
body{{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:linear-gradient(160deg,#2a0845,#5b1a8c 60%,#8a3fc4);min-height:100vh;display:flex;align-items:center;justify-content:center;color:#1d1428}}
.card{{background:#fff;border-radius:18px;padding:28px;width:min(440px,92vw);box-shadow:0 20px 60px rgba(0,0,0,.35)}}
h1{{margin:0 0 4px;font-size:22px;color:#4a1270}} .muted{{color:#6b5c7b;font-size:14px;line-height:1.45}}
label{{display:block;font-size:13px;margin:14px 0 6px;color:#4a3d5a}} input{{width:100%;box-sizing:border-box;padding:11px 12px;border:1px solid #d9cfe6;border-radius:10px;font-size:15px}}
button{{cursor:pointer;border:0;border-radius:10px;padding:11px 14px;font-size:15px;font-weight:600}}
.primary{{background:#5b1a8c;color:#fff;width:100%;margin-top:16px}} .ghost{{background:#f3eef9;color:#4a1270;width:100%;text-align:left;margin-top:8px;font-weight:500}}
.ghost small{{display:block;color:#7b6c8b;font-weight:400}} .row{{display:flex;justify-content:space-between;align-items:center;margin-top:18px}}
.cancel{{background:none;color:#7b6c8b;padding:0;font-weight:500}} .logo{{font-weight:800;letter-spacing:.5px;color:#5b1a8c}} .err{{color:#b3261e;font-size:14px;margin-top:10px}}
</style></head><body><div class="card">
<div class="logo">ФСП ID</div><h1>Вход в профиль участника</h1>
<p class="muted">Приложение <b>{client}</b> запрашивает доступ к вашему профилю и результатам соревнований Федерации спортивного программирования.</p>
{error}
<form method="post" action="{action}">{hidden}
<label>Email или ФСП ID</label><input name="login" placeholder="FSP-100001" autocomplete="username">
<label>Пароль</label><input name="password" type="password" placeholder="для демо-аккаунтов: demo" autocomplete="current-password">
<button class="primary" type="submit">Войти и разрешить доступ</button></form>
<p class="muted" style="margin-top:18px">Демо-аккаунты (тестовая среда):</p>
{demo}
<form method="post" action="{action}">{hidden}<input type="hidden" name="cancel" value="1"><div class="row"><span class="muted">Тестовый стенд, данные вымышлены</span><button class="cancel" type="submit">Отмена</button></div></form>
</div></body></html>"""


def _hidden(fields: dict) -> str:
    return "".join(f'<input type="hidden" name="{k}" value="{html.escape(v)}">' for k, v in fields.items())


@app.get("/realms/{realm}/protocol/openid-connect/auth", response_class=HTMLResponse)
def authorize(realm: str, request: Request, client_id: str, redirect_uri: str, state: str = "",
              response_type: str = "code", scope: str = "openid", error: str = ""):
    if client_id not in CLIENTS:
        raise HTTPException(400, "unknown client_id")
    if response_type != "code":
        raise HTTPException(400, "unsupported response_type")
    fields = {"client_id": client_id, "redirect_uri": redirect_uri, "state": state}
    action = str(request.url_for("authenticate", realm=realm))
    demo = ""
    for p in list(participants().values())[:3]:
        n = len(p["achievements"])
        demo += (f'<form method="post" action="{action}">{_hidden({**fields, "login": p["fsp_id"], "password": "demo"})}'
                 f'<button class="ghost" type="submit">{html.escape(p["full_name"])} · {p["fsp_id"]}'
                 f'<small>{n} достижени{"е" if n == 1 else "я" if 1 < n < 5 else "й"} в реестре</small></button></form>')
    err = f'<div class="err">{html.escape(error)}</div>' if error else ""
    return _PAGE.format(client="ФСП Талант", action=action, hidden=_hidden(fields), demo=demo, error=err)


@app.post("/realms/{realm}/login-actions/authenticate", name="authenticate")
def authenticate(realm: str, request: Request, client_id: str = Form(...), redirect_uri: str = Form(...),
                 state: str = Form(""), login: str = Form(""), password: str = Form(""), cancel: str = Form("")):
    if cancel:
        return RedirectResponse(f"{redirect_uri}?{urlencode({'error': 'access_denied', 'state': state})}", status_code=302)
    login_l = login.strip().lower()
    found = next((p for p in participants().values() if login_l in (p["fsp_id"].lower(), p["email"].lower())), None)
    if found is None or password != "demo":
        q = urlencode({"client_id": client_id, "redirect_uri": redirect_uri, "state": state,
                       "error": "Неверный логин или пароль"})
        return RedirectResponse(f"{request.url_for('authorize', realm=realm)}?{q}", status_code=302)
    code = secrets.token_urlsafe(24)
    _codes[code] = {"fsp_id": found["fsp_id"], "client_id": client_id, "redirect_uri": redirect_uri, "exp": time.time() + 120}
    return RedirectResponse(f"{redirect_uri}?{urlencode({'code': code, 'state': state})}", status_code=302)


@app.post("/realms/{realm}/protocol/openid-connect/token")
def token(realm: str, grant_type: str = Form(...), client_id: str = Form(...), client_secret: str = Form(...),
          code: str = Form(""), redirect_uri: str = Form("")):
    if CLIENTS.get(client_id) != client_secret:
        raise HTTPException(401, "invalid_client")
    if grant_type == "authorization_code":
        rec = _codes.pop(code, None)
        if rec is None or rec["exp"] < time.time() or rec["client_id"] != client_id or rec["redirect_uri"] != redirect_uri:
            raise HTTPException(400, "invalid_grant")
        access = _issue({"sub": rec["fsp_id"], "fsp_id": rec["fsp_id"], "azp": client_id, "typ": "user"})
        return {"access_token": access, "token_type": "Bearer", "expires_in": 600, "scope": "openid profile fsp_achievements"}
    if grant_type == "client_credentials":
        return {"access_token": _issue({"sub": f"service-account-{client_id}", "azp": client_id, "typ": "service"}),
                "token_type": "Bearer", "expires_in": 600}
    raise HTTPException(400, "unsupported_grant_type")


@app.get("/realms/{realm}/protocol/openid-connect/userinfo")
def userinfo(realm: str, authorization: str | None = Header(None)):
    claims = _decode(authorization)
    p = participants().get(claims.get("fsp_id", ""))
    if p is None:
        raise HTTPException(401, "invalid_token")
    return {"sub": p["fsp_id"], "fsp_id": p["fsp_id"], "name": p["full_name"], "email": p["email"],
            "preferred_username": p["fsp_id"].lower(), "region": p["region"]}


@app.get("/api/v1/participants/{fsp_id}/achievements")
def achievements(fsp_id: str, authorization: str | None = Header(None)):
    claims = _decode(authorization)
    if claims.get("typ") == "user" and claims.get("fsp_id") != fsp_id:
        raise HTTPException(403, "Пользовательский токен даёт доступ только к своим достижениям")
    p = participants().get(fsp_id)
    if p is None:
        raise HTTPException(404, "Участник не найден")
    return {"participant": {"fsp_id": p["fsp_id"], "full_name": p["full_name"], "region": p["region"]},
            "achievements": p["achievements"]}


@app.get("/")
def root():
    return {"service": "fsp-mock", "realm_discovery": "/realms/fsp/.well-known/openid-configuration",
            "participants": len(participants())}
