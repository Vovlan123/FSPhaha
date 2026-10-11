"""Схемы запросов и ответов API. Валидация бизнес-правил, которые можно проверить без БД, живёт здесь:
обязательная зарплатная вилка «от–до», коды из справочников, согласие на обработку ПДн."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.dictionaries import (COMPLAINT_CODES, DECLINE_REASON_CODES, GRADE_CODES, INDUSTRY_CODES, ROLE_CODES, SKILLS, SOFT_SKILL_CODES,
                              SPEC_CODES, WORK_FORMAT_CODES)

Grade = Literal["intern", "junior", "middle", "senior"]
Spec = Literal["backend", "frontend", "data", "devops", "qa"]
WorkFormat = Literal["office", "hybrid", "remote"]

ERRORS = {
    401: {"description": "Не авторизован или токен истёк"},
    403: {"description": "Недостаточно прав для роли"},
    404: {"description": "Объект не найден или принадлежит другому пользователю"},
    409: {"description": "Конфликт состояния (ограничение частоты, неверный статус, дубликат)"},
    422: {"description": "Ошибка валидации входных данных"},
}


def _check_codes(values: list[str], allowed: list[str] | dict, what: str) -> list[str]:
    bad = [v for v in values if v not in allowed]
    if bad:
        raise ValueError(f"Неизвестные значения {what}: {', '.join(bad)}")
    return list(dict.fromkeys(values))


class SalaryRange(BaseModel):
    salary_from: int = Field(..., ge=1000, le=10_000_000, description="Нижняя граница, ₽/мес")
    salary_to: int = Field(..., ge=1000, le=10_000_000, description="Верхняя граница, ₽/мес")

    @model_validator(mode="after")
    def _range(self):
        if self.salary_from > self.salary_to:
            raise ValueError("salary_from не может быть больше salary_to")
        return self


# ---------------------------------------------------------------- auth


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    role: Literal["candidate", "employer"]
    consent_pd: bool = Field(..., description="Согласие на обработку персональных данных (152-ФЗ)")

    @field_validator("consent_pd")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Без согласия на обработку персональных данных регистрация невозможна")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    role: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class RegisterOut(BaseModel):
    message: str
    dev_verify_link: str | None = Field(None, description="Только в демо-режиме: ссылка из письма")


class MessageOut(BaseModel):
    message: str


# ---------------------------------------------------------------- кандидат


class ProfileIn(BaseModel):
    full_name: str = Field("", max_length=200)
    phone: str = Field("", max_length=50)
    telegram: str = Field("", max_length=100)
    contact_email: str = Field("", max_length=255)
    city: str = Field("", max_length=100)
    relocation: bool = False
    about: str = Field("", max_length=4000)
    experience_years: float = Field(0, ge=0, le=60)
    roles: list[str] = []
    soft_skills: list[str] = []
    resume_source: Literal["form", "pdf"] = "form"

    _roles = field_validator("roles")(lambda v: _check_codes(v, ROLE_CODES, "ролей"))
    _soft = field_validator("soft_skills")(lambda v: _check_codes(v, SOFT_SKILL_CODES, "софт-скиллов"))


class SurveyIn(BaseModel):
    industries: list[str] = Field(default_factory=list, description="Интересные отрасли")
    specialization: Spec
    stack: list[str] = Field(..., min_length=1, description="Навыки из справочника выбранной специализации")
    experience_years: float = Field(..., ge=0, le=60)
    work_format: list[WorkFormat] = Field(..., min_length=1)
    salary_expect_min: int = Field(..., ge=1000, le=10_000_000)
    city: str = Field("", max_length=100)
    relocation: bool = False
    declared_grade: Grade | None = None

    _ind = field_validator("industries")(lambda v: _check_codes(v, INDUSTRY_CODES, "отраслей"))

    @model_validator(mode="after")
    def _stack(self):
        from app.dictionaries import skills_for_spec
        allowed = skills_for_spec(self.specialization)
        self.stack = _check_codes(self.stack, allowed, "навыков для этой специализации")
        return self


class PrivacyIn(BaseModel):
    show_name: bool = False
    show_salary: bool = True
    show_fsp: bool = True
    show_tasks: bool = True
    hidden_companies: list[str] = Field(default_factory=list, description="Названия компаний, от которых скрыт профиль")
    job_status: Literal["active", "open", "closed"] = "active"
    consent_publish: bool = Field(..., description="Согласие на публикацию профиля работодателям")


class TestStartIn(BaseModel):
    declared_grade: Grade


class AnswerIn(BaseModel):
    item_id: int
    answer_index: int = Field(..., ge=-1, le=9, description="Номер варианта; -1 — время вышло, ответа нет")


class DeclineIn(BaseModel):
    reason: str
    comment: str | None = Field(None, max_length=1000)
    expected_salary: int | None = Field(None, ge=1000, le=10_000_000)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        if v not in DECLINE_REASON_CODES:
            raise ValueError("Неизвестная причина отказа")
        return v


class ComplaintIn(BaseModel):
    reason: str
    comment: str | None = Field(None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def _reason(cls, v: str) -> str:
        if v not in COMPLAINT_CODES:
            raise ValueError("Неизвестная причина жалобы")
        return v


class WebhookIn(BaseModel):
    url: str = Field("", max_length=500, description="URL приёмника в ATS; пустая строка — отключить")

    @field_validator("url")
    @classmethod
    def _url(cls, v: str) -> str:
        v = v.strip()
        if v and not (v.startswith("https://") or v.startswith("http://")):
            raise ValueError("URL должен начинаться с http:// или https://")
        return v


class ApplyIn(BaseModel):
    cover_letter: str = Field("", max_length=3000)


class SubmitIn(BaseModel):
    answer: str = Field(..., min_length=1, max_length=8000)


# ---------------------------------------------------------------- работодатель


class CompanyIn(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: str = Field("", max_length=4000)
    industry: str = ""
    website: str = Field("", max_length=255)
    city: str = Field("", max_length=100)
    size: str = Field("", max_length=32)
    contact_email: str = Field("", max_length=255)
    contact_telegram: str = Field("", max_length=100)
    contact_phone: str = Field("", max_length=50)
    inn: str = Field("", max_length=12, description="ИНН: 10 цифр (юрлицо) или 12 (ИП)")

    @field_validator("inn")
    @classmethod
    def _inn(cls, v: str) -> str:
        v = v.strip()
        if v and not v.isdigit():
            raise ValueError("ИНН состоит только из цифр")
        return v

    @field_validator("industry")
    @classmethod
    def _industry(cls, v: str) -> str:
        if v and v not in INDUSTRY_CODES:
            raise ValueError("Неизвестная отрасль")
        return v


def _skills(v: list[str]) -> list[str]:
    return _check_codes(v, SKILLS, "навыков")


class NeedIn(SalaryRange):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field("", max_length=8000)
    team_about: str = Field("", max_length=4000)
    specialization: Spec
    grade: Grade
    stack_must: list[str] = []
    stack_nice: list[str] = []
    work_format: list[WorkFormat] = []
    city: str = Field("", max_length=100)

    _must = field_validator("stack_must")(_skills)
    _nice = field_validator("stack_nice")(_skills)


class ParseIn(BaseModel):
    text: str = Field(..., min_length=10, max_length=20000)


class InvitationIn(SalaryRange):
    candidate_id: int
    need_id: int | None = None
    vacancy_id: int | None = None
    title: str = Field(..., min_length=3, max_length=200, description="Позиция")
    description: str = Field(..., min_length=10, max_length=6000, description="Описание предложения")
    work_format: list[WorkFormat] = []
    contact_method: str = Field(..., min_length=3, max_length=255, description="Как связаться с работодателем")


class VacancyIn(SalaryRange):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field("", max_length=8000)
    specialization: Spec
    grade: Grade
    stack: list[str] = []
    work_format: list[WorkFormat] = []
    city: str = Field("", max_length=100)
    status: Literal["published", "closed"] = "published"

    _stack = field_validator("stack")(_skills)


class AppStatusIn(BaseModel):
    status: Literal["viewed", "invited", "rejected"]


class RubricPoint(BaseModel):
    point: str = Field(..., min_length=2, max_length=300)
    keywords: list[str] = Field(..., min_length=1)


class TaskIn(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    body: str = Field(..., min_length=10, max_length=8000)
    kind: Literal["solve", "approach"] = "approach"
    specialization: Spec
    grades: list[Grade] = []
    rubric: list[RubricPoint] = Field(..., min_length=1)


class RateIn(BaseModel):
    score: int = Field(..., ge=1, le=5)


class SelectionFilter(BaseModel):
    stack: list[str] = []
    has_fsp: bool = False
    confident_only: bool = False
    salary_fit: bool = False
    pinned_only: bool = False
    min_score: float = 0


__all__ = [n for n in dir() if n[0].isupper()] + ["ERRORS", "GRADE_CODES", "SPEC_CODES", "WORK_FORMAT_CODES"]
