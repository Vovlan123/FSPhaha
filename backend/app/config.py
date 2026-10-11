"""Настройки приложения. Все значения берутся из переменных окружения с безопасными для демо значениями по умолчанию."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


class Settings:
    database_url: str = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'data' / 'app.db'}")
    secret_key: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production-0123456789")
    token_ttl_hours: int = int(os.getenv("TOKEN_TTL_HOURS", "12"))

    # Публичные адреса: фронтенд (для ссылок в письмах и редиректов) и бэкенд (для redirect_uri OAuth)
    frontend_url: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    backend_public_url: str = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    cors_origins: list[str] = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

    # Почта: без SMTP_HOST письма пишутся в лог
    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = int(os.getenv("SMTP_PORT", "1025"))
    smtp_from: str = os.getenv("SMTP_FROM", "no-reply@fsp-talent.local")
    # Демо-режим: ссылка подтверждения возвращается в ответе API, чтобы жюри не искало письмо
    demo_expose_links: bool = _bool("DEMO_EXPOSE_LINKS", True)

    # ФСП ID (OIDC, совместимо с Keycloak). Браузерный адрес и серверный адрес могут различаться (Docker)
    fsp_base_url: str = os.getenv("FSP_BASE_URL", "http://localhost:8000/fsp")
    fsp_internal_url: str = os.getenv("FSP_INTERNAL_URL", "")
    fsp_realm: str = os.getenv("FSP_REALM", "fsp")
    fsp_client_id: str = os.getenv("FSP_CLIENT_ID", "fsp-talent")
    fsp_client_secret: str = os.getenv("FSP_CLIENT_SECRET", "fsp-talent-secret")
    # Встроить mock-реестр ФСП в процесс бэкенда (удобно для локального запуска без второго процесса)
    fsp_mock_embedded: bool = _bool("FSP_MOCK_EMBEDDED", True)
    # Использовать системные/переменные прокси при обращении к ФСП. По умолчанию выключено: системный прокси
    # (например, VPN-клиент на macOS) иначе перехватывает даже запросы к localhost.
    fsp_trust_env: bool = _bool("FSP_HTTP_TRUST_ENV", False)

    # Правила тестирования (см. spec.md, «Механика тестирования»)
    grade_change_cooldown_days: int = int(os.getenv("GRADE_COOLDOWN_DAYS", "90"))
    retest_same_grade_days: int = int(os.getenv("RETEST_SAME_GRADE_DAYS", "30"))
    upgrade_accept_window_days: int = 7
    seen_template_window_days: int = 180
    item_time_limit_sec: int = 120
    item_time_grace_sec: int = 10
    attempt_abandon_minutes: int = 30
    test_min_items: int = 10
    test_max_items: int = 20

    # Правила подбора и приглашений
    invite_quota_week: int = int(os.getenv("INVITE_QUOTA_WEEK", "20"))
    invite_quota_unverified: int = int(os.getenv("INVITE_QUOTA_UNVERIFIED", "5"))
    complaints_to_suspend: int = int(os.getenv("COMPLAINTS_TO_SUSPEND", "3"))
    # Куда демо-работодатель шлёт вебхуки (встроенный приёмник, имитирующий ATS)
    demo_webhook_url: str = os.getenv("DEMO_WEBHOOK_URL", "http://localhost:8000/api/system/webhook-echo")
    invite_ttl_days: int = 14
    task_interval_days: int = int(os.getenv("TASK_INTERVAL_DAYS", "7"))

    pdf_font_path: str = os.getenv("PDF_FONT_PATH", "")

    @property
    def fsp_server_url(self) -> str:
        return self.fsp_internal_url or self.fsp_base_url


settings = Settings()
