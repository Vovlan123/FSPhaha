from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.common import iso
from app.db import get_db
from app.models import CandidateProfile, TestAttempt
from app.schemas import ERRORS, AnswerIn, TestStartIn
from app.security import current_candidate
from app.services import testing

router = APIRouter(prefix="/tests", tags=["Тестирование"], responses=ERRORS)


def _own(db: Session, cand: CandidateProfile, attempt_id: int) -> TestAttempt:
    att = db.get(TestAttempt, attempt_id)
    if att is None or att.candidate_id != cand.id:
        raise HTTPException(404, "Попытка не найдена")
    return att


@router.get("/availability", summary="Доступность теста на каждый грейд (ограничения частоты)")
def availability(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    av = testing.availability(db, cand)
    db.commit()
    return [{"grade": a.grade, "allowed": a.allowed, "reason": a.reason, "available_at": iso(a.available_at)} for a in av]


@router.post("/start", summary="Начать адаптивный тест на заявленный грейд",
             responses={409: {"description": "Тест на этот грейд сейчас недоступен; в detail.available_at — когда станет доступен"}})
def start(body: TestStartIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    att = testing.start_attempt(db, cand, body.declared_grade)
    return testing.attempt_public(att)


@router.get("/active", summary="Текущая незавершённая попытка (или null)")
def active(cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    att = testing.active_attempt(db, cand)
    db.commit()
    return testing.attempt_public(att) if att else None


@router.get("/{attempt_id}", summary="Состояние попытки: текущий вопрос или результат")
def get_attempt(attempt_id: int, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    return testing.attempt_public(_own(db, cand, attempt_id))


@router.post("/{attempt_id}/answer", summary="Ответить на текущий вопрос. Верный ответ клиенту не раскрывается")
def answer(attempt_id: int, body: AnswerIn, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    att = testing.submit_answer(db, _own(db, cand, attempt_id), body.item_id, body.answer_index)
    return testing.attempt_public(att)


@router.post("/{attempt_id}/accept-upgrade", summary="Принять грейд выше по результату уверенной попытки")
def accept_upgrade(attempt_id: int, cand: CandidateProfile = Depends(current_candidate), db: Session = Depends(get_db)):
    att = _own(db, cand, attempt_id)
    testing.accept_upgrade(db, cand, att)
    return testing.attempt_public(att)
