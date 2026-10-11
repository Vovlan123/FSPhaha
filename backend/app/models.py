"""Модели данных. Состав и смысл полей — см. spec.md, раздел «Сущности».

Все даты хранятся как naive UTC (совместимо и с SQLite, и с PostgreSQL).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def default_privacy() -> dict:
    return {"show_name": False, "show_salary": True, "show_fsp": True, "show_tasks": True, "hidden_companies": []}


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16))  # candidate | employer
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verify_token_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    consent_pd_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    candidate: Mapped["CandidateProfile | None"] = relationship(back_populates="user", uselist=False)
    company: Mapped["Company | None"] = relationship(back_populates="user", uselist=False)


class CandidateProfile(Base):
    __tablename__ = "candidate_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    anon_code: Mapped[str] = mapped_column(String(16), unique=True)

    full_name: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")
    telegram: Mapped[str] = mapped_column(String(100), default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    relocation: Mapped[bool] = mapped_column(Boolean, default=False)
    about: Mapped[str] = mapped_column(Text, default="")
    experience_years: Mapped[float] = mapped_column(Float, default=0.0)
    roles: Mapped[list] = mapped_column(JSON, default=list)
    soft_skills: Mapped[list] = mapped_column(JSON, default=list)
    industries: Mapped[list] = mapped_column(JSON, default=list)

    specialization: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    stack: Mapped[list] = mapped_column(JSON, default=list)
    work_format: Mapped[list] = mapped_column(JSON, default=list)
    salary_expect_min: Mapped[int | None] = mapped_column(Integer, nullable=True)

    grade: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    theta_se: Mapped[float | None] = mapped_column(Float, nullable=True)
    grade_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    verified_topics: Mapped[dict] = mapped_column(JSON, default=dict)

    job_status: Mapped[str] = mapped_column(String(16), default="active")
    consent_publish_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    privacy: Mapped[dict] = mapped_column(JSON, default=default_privacy)

    fsp_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fsp_linked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fsp_achievements: Mapped[list] = mapped_column(JSON, default=list)
    fsp_fetched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    resume_source: Mapped[str] = mapped_column(String(8), default="form")
    onboarding_done: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship(back_populates="candidate")


class SurveyResponse(Base):
    __tablename__ = "survey_responses"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    answers: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class TestAttempt(Base):
    __tablename__ = "test_attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    specialization: Mapped[str] = mapped_column(String(32))
    declared_grade: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="in_progress")
    theta: Mapped[float | None] = mapped_column(Float, nullable=True)
    se: Mapped[float | None] = mapped_column(Float, nullable=True)
    n_items: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str | None] = mapped_column(String(16), nullable=True)
    upgrade_grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    suggested_grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    upgrade_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    focus_topics: Mapped[list] = mapped_column(JSON, default=list)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["TestItem"]] = relationship(back_populates="attempt", order_by="TestItem.order")


class TestItem(Base):
    __tablename__ = "test_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    attempt_id: Mapped[int] = mapped_column(ForeignKey("test_attempts.id"), index=True)
    template_id: Mapped[str] = mapped_column(String(64), index=True)
    seed: Mapped[int] = mapped_column(Integer)
    order: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    correct_index: Mapped[int] = mapped_column(Integer)  # никогда не отдаётся клиенту
    served_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    answer_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timed_out: Mapped[bool] = mapped_column(Boolean, default=False)
    theta_after: Mapped[float | None] = mapped_column(Float, nullable=True)
    se_after: Mapped[float | None] = mapped_column(Float, nullable=True)

    attempt: Mapped[TestAttempt] = relationship(back_populates="items")


class TemplateStat(Base):
    __tablename__ = "template_stats"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    exposures: Mapped[int] = mapped_column(Integer, default=0)
    correct: Mapped[int] = mapped_column(Integer, default=0)
    residuals: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16), default="active")
    flagged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GradeEvent(Base):
    __tablename__ = "grade_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    from_grade: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_grade: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(16))
    attempt_id: Mapped[int | None] = mapped_column(ForeignKey("test_attempts.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(32), default="")
    website: Mapped[str] = mapped_column(String(255), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    size: Mapped[str] = mapped_column(String(32), default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    contact_telegram: Mapped[str] = mapped_column(String(100), default="")
    contact_phone: Mapped[str] = mapped_column(String(50), default="")
    invite_quota_week: Mapped[int] = mapped_column(Integer, default=20)
    # Защита от недобросовестных работодателей: верификация компании (ИНН + корпоративный домен)
    inn: Mapped[str] = mapped_column(String(12), default="")
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Интеграция с ATS: исходящие вебхуки с HMAC-подписью
    webhook_url: Mapped[str] = mapped_column(String(500), default="")
    webhook_secret: Mapped[str] = mapped_column(String(64), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    user: Mapped[User] = relationship(back_populates="company")


class Need(Base):
    __tablename__ = "needs"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    team_about: Mapped[str] = mapped_column(Text, default="")
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(16))
    stack_must: Mapped[list] = mapped_column(JSON, default=list)
    stack_nice: Mapped[list] = mapped_column(JSON, default=list)
    work_format: Mapped[list] = mapped_column(JSON, default=list)
    city: Mapped[str] = mapped_column(String(100), default="")
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    selection_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class SelectionItem(Base):
    __tablename__ = "selection_items"
    __table_args__ = (UniqueConstraint("need_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    need_id: Mapped[int] = mapped_column(ForeignKey("needs.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"))
    score: Mapped[float] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON, default=dict)
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    rank: Mapped[int] = mapped_column(Integer, default=0)


class Invitation(Base):
    __tablename__ = "invitations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    need_id: Mapped[int | None] = mapped_column(ForeignKey("needs.id"), nullable=True)
    vacancy_id: Mapped[int | None] = mapped_column(ForeignKey("vacancies.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    work_format: Mapped[list] = mapped_column(JSON, default=list)
    contact_method: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(16), default="sent", index=True)
    below_expectations: Mapped[bool] = mapped_column(Boolean, default=False)
    decline_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    decline_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_salary: Mapped[int | None] = mapped_column(Integer, nullable=True)
    complaint_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    complaint_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    complaint_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime)

    company: Mapped[Company] = relationship()
    candidate: Mapped[CandidateProfile] = relationship()


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    specialization: Mapped[str] = mapped_column(String(32))
    grade: Mapped[str] = mapped_column(String(16))
    stack: Mapped[list] = mapped_column(JSON, default=list)
    work_format: Mapped[list] = mapped_column(JSON, default=list)
    city: Mapped[str] = mapped_column(String(100), default="")
    salary_from: Mapped[int] = mapped_column(Integer)
    salary_to: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="published")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    company: Mapped[Company] = relationship()


class Application(Base):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("vacancy_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    cover_letter: Mapped[str] = mapped_column(Text, default="")
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="sent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    vacancy: Mapped[Vacancy] = relationship()
    candidate: Mapped[CandidateProfile] = relationship()


class RegularTask(Base):
    __tablename__ = "regular_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(String(16), default="approach")  # solve | approach
    specialization: Mapped[str] = mapped_column(String(32))
    grades: Mapped[list] = mapped_column(JSON, default=list)
    rubric: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    company: Mapped[Company] = relationship()


class TaskAssignment(Base):
    __tablename__ = "task_assignments"
    __table_args__ = (UniqueConstraint("task_id", "candidate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("regular_tasks.id"), index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidate_profiles.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="assigned")
    answer: Mapped[str] = mapped_column(Text, default="")
    auto_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    rubric_hits: Mapped[list] = mapped_column(JSON, default=list)
    employer_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped[RegularTask] = relationship()
    candidate: Mapped[CandidateProfile] = relationship()


class OAuthState(Base):
    """Одноразовый state для OAuth-потока привязки ФСП ID: связывает возврат из ФСП с пользователем."""

    __tablename__ = "oauth_states"

    state: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class WebhookDelivery(Base):
    """Журнал доставок вебхуков в ATS работодателя."""

    __tablename__ = "webhook_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)
    event: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | delivered | failed
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
