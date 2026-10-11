from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.dictionaries import GRADE_CODES, SPEC_CODES, public_dictionaries, skill_label
from app.models import Company, TemplateStat, WebhookDelivery
from app.services.bank import REGISTRY
from app.services.testing import blueprint
from app.services.webhooks import sign

router = APIRouter(tags=["Справочники и система"])


@router.get("/meta/dictionaries", summary="Справочники: специализации, грейды, навыки, отрасли, статусы")
def dictionaries():
    return public_dictionaries()


@router.get("/system/health", summary="Проверка работоспособности")
def health():
    return {"status": "ok", "templates": len(REGISTRY)}


@router.get("/system/bank-health", summary="Состояние банка заданий и детектор утечек")
def bank_health(db: Session = Depends(get_db)):
    """По каждому шаблону: параметры IRT, число показов, доля верных, средний остаток «ответ − ожидание модели»
    по последним показам и статус. Шаблон уходит в карантин, если по нему систематически отвечают лучше,
    чем предсказывает модель, — признак утечки приёма решения."""
    stats = {s.template_id: s for s in db.execute(select(TemplateStat)).scalars()}
    rows = []
    for t in REGISTRY.values():
        st = stats.get(t.id)
        res = list(st.residuals or []) if st else []
        rows.append({
            "id": t.id, "pool": t.pool, "title": t.title, "fmt": t.fmt, "a": t.a, "b": t.b, "variants": t.variants,
            "topics": [skill_label(x) for x in t.topics],
            "exposures": st.exposures if st else 0,
            "p_correct": round(st.correct / st.exposures, 3) if st and st.exposures else None,
            "mean_residual": round(sum(res) / len(res), 3) if res else None,
            "status": st.status if st else "active",
            "flagged_at": st.flagged_at.isoformat() + "Z" if st and st.flagged_at else None,
        })
    rows.sort(key=lambda r: (r["pool"], r["b"]))
    return {"total": len(rows), "quarantined": sum(1 for r in rows if r["status"] == "quarantine"), "templates": rows}


@router.get("/system/blueprint", summary="Демонстрация: план теста для специализации, грейда и стека (без авторизации)")
def demo_blueprint(specialization: str = "backend", grade: str = "middle", stack: str = "python,sql,postgresql"):
    if specialization not in SPEC_CODES or grade not in GRADE_CODES:
        raise HTTPException(422, "Неизвестная специализация или грейд")
    return blueprint(specialization, grade, [s.strip() for s in stack.split(",") if s.strip()])


_ECHO: deque = deque(maxlen=50)


@router.post("/system/webhook-echo", summary="Демо-приёмник вебхуков (имитирует ATS): проверяет подпись и запоминает событие",
             tags=["Интеграция с ATS"])
async def webhook_echo(request: Request, db: Session = Depends(get_db)):
    body = await request.body()
    delivery = db.get(WebhookDelivery, int(request.headers.get("X-FSP-Delivery", "0") or 0))
    company = db.get(Company, delivery.company_id) if delivery else None
    valid = bool(company and request.headers.get("X-FSP-Signature") == sign(company.webhook_secret, body))
    _ECHO.appendleft({"event": request.headers.get("X-FSP-Event"), "delivery": request.headers.get("X-FSP-Delivery"),
                      "signature_valid": valid, "bytes": len(body)})
    if not valid:
        raise HTTPException(401, "Неверная подпись")
    return {"received": True}


@router.get("/system/webhook-echo", summary="Последние события, полученные демо-приёмником", tags=["Интеграция с ATS"])
def webhook_echo_log():
    return list(_ECHO)

