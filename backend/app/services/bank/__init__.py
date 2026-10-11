"""Банк параметрических шаблонов. Импорт пулов регистрирует шаблоны в REGISTRY."""
from app.services.bank.base import POOLS, REGISTRY, ItemInstance, Template  # noqa: F401
from app.services.bank import pool_core, pool_backend, pool_frontend, pool_data, pool_devops, pool_qa  # noqa: F401,E402


def templates_for_spec(spec: str) -> list[Template]:
    """Шаблоны, доступные в тесте по специализации: общий пул + пул специализации."""
    return [t for t in REGISTRY.values() if t.pool in ("core", spec)]
