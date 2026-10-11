import secrets
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import CandidateProfile, OAuthState, User, utcnow
from app.schemas import ERRORS
from app.security import current_candidate, current_user
from app.services import fsp_client, matching

router = APIRouter(prefix="/fsp", tags=["Интеграция с ФСП ID"], responses=ERRORS)


@router.post("/link/start", summary="Начать привязку ФСП ID: вернёт ссылку на страницу входа ФСП (OIDC)")
def link_start(user: User = Depends(current_user), cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    state = secrets.token_urlsafe(24)
    db.execute(delete(OAuthState).where(OAuthState.created_at < utcnow() - timedelta(minutes=10)))
    db.add(OAuthState(state=state, user_id=user.id))
    db.commit()
    return {"authorize_url": fsp_client.authorize_url(state)}


def _front(status: str, message: str = "") -> RedirectResponse:
    q = urlencode({"fsp": status, **({"message": message} if message else {})})
    return RedirectResponse(f"{settings.frontend_url}/candidate/settings?{q}", status_code=302)


@router.get("/callback", summary="Возврат из ФСП ID (redirect_uri). Без авторизации: пользователь определяется по state")
def callback(state: str, code: str | None = None, error: str | None = None, db: Session = Depends(get_db)):
    st = db.get(OAuthState, state)
    if st is None or utcnow() - st.created_at > timedelta(minutes=10):
        return _front("error", "Сессия привязки истекла, попробуйте ещё раз")
    user_id = st.user_id
    db.delete(st)
    db.commit()
    if error or not code:
        return _front("cancelled", "Вход в ФСП ID отменён")
    cand = db.execute(select(CandidateProfile).where(CandidateProfile.user_id == user_id)).scalar_one_or_none()
    if cand is None:
        return _front("error", "Профиль кандидата не найден")
    try:
        token = fsp_client.exchange_code(code)
        info = fsp_client.userinfo(token)
        fsp_id = info.get("fsp_id") or info["sub"]
        taken = db.execute(select(CandidateProfile.id).where(CandidateProfile.fsp_id == fsp_id, CandidateProfile.id != cand.id)).first()
        if taken:
            return _front("error", "Этот ФСП ID уже привязан к другому профилю")
        ach = fsp_client.achievements(fsp_id, token)
    except fsp_client.FspError as e:
        return _front("error", str(e))
    cand.fsp_id, cand.fsp_linked_at = fsp_id, utcnow()
    cand.fsp_achievements, cand.fsp_fetched_at = ach, utcnow()
    db.commit()
    return _front("linked")


@router.post("/refresh", summary="Обновить достижения из реестра ФСП (client credentials)")
def refresh(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    if not cand.fsp_id:
        raise HTTPException(409, "Профиль не связан с ФСП ID")
    try:
        cand.fsp_achievements = fsp_client.achievements(cand.fsp_id, fsp_client.service_token())
    except fsp_client.FspError as e:
        raise HTTPException(502, str(e)) from e
    cand.fsp_fetched_at = utcnow()
    db.commit()
    return matching.fsp_public(cand, for_employer=False)


@router.delete("/link", summary="Отвязать ФСП ID и удалить снимок достижений")
def unlink(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    cand.fsp_id = cand.fsp_linked_at = cand.fsp_fetched_at = None
    cand.fsp_achievements = []
    db.commit()
    return matching.fsp_public(cand, for_employer=False)
