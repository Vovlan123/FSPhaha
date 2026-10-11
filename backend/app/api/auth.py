import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.emailer import send_email
from app.models import CandidateProfile, Company, User, utcnow
from app.schemas import ERRORS, LoginIn, MessageOut, RegisterIn, RegisterOut, TokenOut, UserOut
from app.security import create_access_token, current_user, hash_password, hash_token, verify_password

router = APIRouter(prefix="/auth", tags=["Авторизация"], responses=ERRORS)


def next_anon_code(db: Session) -> str:
    n = (db.execute(select(func.count(CandidateProfile.id))).scalar() or 0) + 1001
    while db.execute(select(CandidateProfile.id).where(CandidateProfile.anon_code == f"К-{n}")).first():
        n += 1
    return f"К-{n}"


def _send_verification(user: User, token: str) -> str:
    link = f"{settings.frontend_url}/verify?token={token}"
    send_email(user.email, "Подтвердите email — ФСП Талант",
               f"Здравствуйте!\n\nЧтобы завершить регистрацию на платформе ФСП Талант, перейдите по ссылке:\n{link}\n\n"
               "Если вы не регистрировались, просто проигнорируйте письмо.")
    return link


@router.post("/register", response_model=RegisterOut, status_code=201, summary="Регистрация по email")
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.lower()
    if db.execute(select(User.id).where(User.email == email)).first():
        raise HTTPException(409, "Пользователь с таким email уже зарегистрирован")
    token = secrets.token_urlsafe(32)
    user = User(email=email, password_hash=hash_password(body.password), role=body.role, email_verified=False,
                verify_token_hash=hash_token(token), consent_pd_at=utcnow())
    db.add(user)
    db.flush()
    if body.role == "candidate":
        db.add(CandidateProfile(user_id=user.id, anon_code=next_anon_code(db), contact_email=email))
    else:
        db.add(Company(user_id=user.id, contact_email=email, invite_quota_week=settings.invite_quota_week))
    db.commit()
    link = _send_verification(user, token)
    return RegisterOut(message="Мы отправили письмо со ссылкой подтверждения на ваш email",
                       dev_verify_link=link if settings.demo_expose_links else None)


@router.get("/verify", response_model=TokenOut, summary="Подтверждение email по токену из письма")
def verify(token: str, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.verify_token_hash == hash_token(token))).scalar_one_or_none()
    if user is None:
        raise HTTPException(404, "Ссылка недействительна или уже использована")
    user.email_verified = True
    user.verify_token_hash = None
    db.commit()
    return TokenOut(access_token=create_access_token(user), user=UserOut(id=user.id, email=user.email, role=user.role))


@router.post("/resend", response_model=RegisterOut, summary="Повторно отправить письмо подтверждения")
def resend(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    if user.email_verified:
        raise HTTPException(409, "Email уже подтверждён")
    token = secrets.token_urlsafe(32)
    user.verify_token_hash = hash_token(token)
    db.commit()
    link = _send_verification(user, token)
    return RegisterOut(message="Письмо отправлено повторно", dev_verify_link=link if settings.demo_expose_links else None)


@router.post("/login", response_model=TokenOut, summary="Вход")
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == body.email.lower())).scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "Неверный email или пароль")
    if not user.email_verified:
        raise HTTPException(403, "Подтвердите email: ссылка отправлена в письме при регистрации")
    return TokenOut(access_token=create_access_token(user), user=UserOut(id=user.id, email=user.email, role=user.role))


@router.get("/me", response_model=UserOut, summary="Текущий пользователь")
def me(user: User = Depends(current_user)):
    return UserOut(id=user.id, email=user.email, role=user.role)


@router.post("/logout", response_model=MessageOut, summary="Выход (токен удаляется на клиенте)")
def logout():
    return MessageOut(message="ok")
