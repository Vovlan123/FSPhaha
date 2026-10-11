"""Пароли (scrypt), токены (JWT HS256) и зависимости FastAPI для проверки ролей."""
import base64
import hashlib
import hmac
import secrets
from datetime import timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import CandidateProfile, Company, User, utcnow

_SCRYPT = {"n": 2**14, "r": 8, "p": 1, "dklen": 32}


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return "scrypt$" + base64.b64encode(salt).decode() + "$" + base64.b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_b64, dk_b64 = stored.split("$")
        salt, expected = base64.b64decode(salt_b64), base64.b64decode(dk_b64)
    except ValueError:
        return False
    dk = hashlib.scrypt(password.encode(), salt=salt, **_SCRYPT)
    return hmac.compare_digest(dk, expected)


def hash_token(token: str) -> str:
    """Токены подтверждения храним только в виде хэша — утечка БД не даёт подтвердить чужой email."""
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user: User) -> str:
    now = utcnow()
    payload = {"sub": str(user.id), "role": user.role, "iat": now, "exp": now + timedelta(hours=settings.token_ttl_hours)}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


_bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Требуется авторизация")
    try:
        payload = jwt.decode(creds.credentials, settings.secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Недействительный или истёкший токен") from None
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.email_verified:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Пользователь не найден или email не подтверждён")
    return user


def current_candidate(user: User = Depends(current_user), db: Session = Depends(get_db)) -> CandidateProfile:
    if user.role != "candidate":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только кандидатам")
    profile = db.query(CandidateProfile).filter_by(user_id=user.id).one_or_none()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Профиль кандидата не найден")
    return profile


def current_employer_user(user: User = Depends(current_user)) -> User:
    if user.role != "employer":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Доступно только работодателям")
    return user


def current_company(user: User = Depends(current_employer_user), db: Session = Depends(get_db)) -> Company:
    """Компания работодателя; подбор недоступен, пока профиль компании не заполнен (нет названия)."""
    company = db.query(Company).filter_by(user_id=user.id).one_or_none()
    if company is None or not company.name.strip():
        raise HTTPException(status.HTTP_409_CONFLICT, "Сначала заполните профиль компании")
    return company
