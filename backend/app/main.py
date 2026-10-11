"""ФСП Талант — API платформы подбора ИТ-специалистов с верифицированным профилем.

OpenAPI: /docs (Swagger UI), /redoc, /openapi.json.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, candidate, employer, fsp, meta, tests, vacancies
from app.config import settings
from app.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logging.getLogger("fontTools").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ФСП Талант API",
    version="0.1.0",
    description=(
        "Платформа подбора ИТ-специалистов с обратной механикой: кандидат проходит опрос и адаптивный тест, "
        "получает категорию «специализация × грейд», работодатель находит его в категоризированной базе и "
        "отправляет приглашение с обязательной зарплатной вилкой. Профиль обогащается достижениями ФСП.\n\n"
        "Авторизация: `Authorization: Bearer <token>` из `/api/auth/login` или `/api/auth/verify`."
    ),
    lifespan=lifespan,
)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

for r in (auth.router, meta.router, candidate.router, tests.router, vacancies.router, employer.router, fsp.router):
    app.include_router(r, prefix="/api")

if settings.fsp_mock_embedded:
    from fsp_mock.main import app as fsp_mock_app

    app.mount("/fsp", fsp_mock_app)
