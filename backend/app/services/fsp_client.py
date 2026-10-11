"""Клиент реестра ФСП: OAuth 2.0 / OpenID Connect в формате Keycloak.

Привязка ФСП ID — authorization code flow:
  1. /api/fsp/link/start → ссылка на {FSP}/realms/{realm}/protocol/openid-connect/auth со state;
  2. пользователь входит в ФСП ID и возвращается на /api/fsp/callback?code&state;
  3. бэкенд меняет code на токен, читает userinfo (fsp_id) и достижения участника.
Обновление достижений — client credentials (сервисный аккаунт клиента в Keycloak).
Переход на боевой Keycloak ФСП: сменить FSP_BASE_URL, FSP_REALM, FSP_CLIENT_ID, FSP_CLIENT_SECRET.
"""
from __future__ import annotations

from urllib.parse import urlencode

import httpx

from app.config import settings


class FspError(Exception):
    pass


def _http() -> httpx.Client:
    return httpx.Client(timeout=10, trust_env=settings.fsp_trust_env)


def _oidc(base: str, path: str) -> str:
    return f"{base}/realms/{settings.fsp_realm}/protocol/openid-connect/{path}"


def redirect_uri() -> str:
    return f"{settings.backend_public_url}/api/fsp/callback"


def authorize_url(state: str) -> str:
    q = urlencode({"client_id": settings.fsp_client_id, "redirect_uri": redirect_uri(), "response_type": "code",
                   "scope": "openid profile fsp_achievements", "state": state})
    return f"{_oidc(settings.fsp_base_url, 'auth')}?{q}"


def _post_token(data: dict) -> str:
    try:
        with _http() as http:
            r = http.post(_oidc(settings.fsp_server_url, "token"), data={
                **data, "client_id": settings.fsp_client_id, "client_secret": settings.fsp_client_secret})
    except httpx.HTTPError as e:
        raise FspError(f"Реестр ФСП недоступен: {e}") from e
    if r.status_code != 200:
        raise FspError(f"ФСП отклонил запрос токена: {r.status_code} {r.text[:200]}")
    return r.json()["access_token"]


def exchange_code(code: str) -> str:
    return _post_token({"grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri()})


def service_token() -> str:
    return _post_token({"grant_type": "client_credentials"})


def userinfo(token: str) -> dict:
    try:
        with _http() as http:
            r = http.get(_oidc(settings.fsp_server_url, "userinfo"), headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise FspError(f"Реестр ФСП недоступен: {e}") from e
    if r.status_code != 200:
        raise FspError(f"Не удалось получить профиль ФСП: {r.status_code}")
    return r.json()


def achievements(fsp_id: str, token: str) -> list[dict]:
    try:
        with _http() as http:
            r = http.get(f"{settings.fsp_server_url}/api/v1/participants/{fsp_id}/achievements",
                         headers={"Authorization": f"Bearer {token}"})
    except httpx.HTTPError as e:
        raise FspError(f"Реестр ФСП недоступен: {e}") from e
    if r.status_code == 404:
        return []
    if r.status_code != 200:
        raise FspError(f"Не удалось получить достижения: {r.status_code}")
    return r.json().get("achievements", [])
