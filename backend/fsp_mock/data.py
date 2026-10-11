"""Синтетический реестр ФСП: мероприятия и участники с результатами.

Структура данных — предложение команды (ТЗ не задаёт её намеренно). Для работодателя важны:
что за соревнование (дисциплина, уровень), какой результат (место, статус), когда, в какой команде и роли.
Все данные вымышлены и генерируются детерминированно (seed=2026).
"""
from __future__ import annotations

import random
from functools import lru_cache

DISCIPLINES = ["algorithmic", "product", "security", "robotics", "uav"]

_EVENT_TEMPLATES = [
    ("Чемпионат по продуктовому программированию", "product", "national"),
    ("Кубок по алгоритмическому программированию", "algorithmic", "national"),
    ("Командный турнир по программированию систем ИБ", "security", "national"),
    ("Окружные соревнования по продуктовому программированию", "product", "interregional"),
    ("Региональный этап по алгоритмическому программированию", "algorithmic", "regional"),
    ("Хакатон «Цифровой регион»", "product", "regional"),
    ("Открытые соревнования по программированию БАС", "uav", "national"),
    ("Турнир по программированию робототехники", "robotics", "interregional"),
    ("Международный командный контест", "algorithmic", "international"),
    ("Городской кибертурнир CTF", "security", "local"),
    ("Студенческий хакатон по ML-продуктам", "product", "local"),
    ("Межвузовская олимпиада по программированию", "algorithmic", "regional"),
]
REGIONS = ["Москва", "Санкт-Петербург", "Казань", "Новосибирск", "Екатеринбург", "Нижний Новгород", "Томск",
           "Самара", "Краснодар", "Пермь", "Иннополис", "Владивосток"]
FIRST = ["Алексей", "Мария", "Дмитрий", "Анна", "Иван", "Екатерина", "Сергей", "Ольга", "Никита", "Полина", "Артём",
         "Дарья", "Михаил", "Софья", "Кирилл", "Алина", "Егор", "Виктория", "Максим", "Ксения", "Тимур", "Вероника"]
LAST_M = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров",
          "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев"]
FEMALE = {"Мария", "Анна", "Екатерина", "Ольга", "Полина", "Дарья", "Софья", "Алина", "Виктория", "Ксения", "Вероника"}
TEAMS = ["Синтаксис", "Нулевой указатель", "Бинарный поиск", "Код Ржевского", "Байтовый поток", "Стек вызовов",
         "Кэш-промах", "Гонка данных", "Флаг ОК", "Рекурсия", "Альфа-ветка", "Пиксель"]


def surname(first: str, last: str) -> str:
    return last + "а" if first in FEMALE else last


@lru_cache
def events() -> list[dict]:
    rng = random.Random(2026)
    out = []
    n = 1
    for year in range(2021, 2027):
        for name, disc, level in _EVENT_TEMPLATES:
            if rng.random() < 0.75:
                month = rng.randint(2, 11) if year < 2026 else rng.randint(2, 8)
                out.append({"event_id": f"EV-{year}-{n:03d}", "event_name": f"{name} {year}", "discipline": disc,
                            "level": level, "date": f"{year}-{month:02d}-{rng.randint(1, 28):02d}",
                            "event_type": "hackathon" if "акатон" in name else "competition"})
                n += 1
    return out


def _result(rng: random.Random, strength: float) -> tuple[str, int | None]:
    r = rng.random() * (0.6 + strength)
    if r > 1.25:
        return "winner", 1
    if r > 0.95:
        return "prize", rng.choice([2, 3])
    if r > 0.65:
        return "finalist", rng.randint(4, 15)
    return "participant", None


def _achievements(rng: random.Random, k: int, strength: float, prefer: list[str] | None = None) -> list[dict]:
    evs = events()
    if prefer:
        pool = [e for e in evs if e["discipline"] in prefer] or evs
    else:
        pool = evs
    chosen = rng.sample(pool, min(k, len(pool)))
    team = rng.choice(TEAMS)
    out = []
    for e in sorted(chosen, key=lambda x: x["date"]):
        res, place = _result(rng, strength)
        out.append({**e, "result": res, "place": place, "team_name": team if rng.random() < 0.8 else rng.choice(TEAMS),
                    "team_role": "captain" if rng.random() < 0.3 else "member"})
    return out


@lru_cache
def participants() -> dict[str, dict]:
    """fsp_id → участник. Первые три записи — демо-аккаунты на странице входа ФСП ID, четвёртая занята демо-кандидатом."""
    rng = random.Random(4242)
    out: dict[str, dict] = {}
    demo = [
        ("FSP-100001", "Алексей", "Смирнов", 4, 0.9, ["product", "algorithmic"]),
        ("FSP-100002", "Мария", "Лебедев", 2, 0.5, ["security"]),
        ("FSP-100003", "Иван", "Новиков", 0, 0.0, None),  # участник без достижений — проверка пустого состояния
        ("FSP-100004", "Дарья", "Орлов", 3, 0.8, ["product", "algorithmic"]),  # привязан к демо-кандидату в seed
    ]
    for fsp_id, first, last, k, s, pref in demo:
        out[fsp_id] = {"fsp_id": fsp_id, "full_name": f"{surname(first, last)} {first}", "email": f"{fsp_id.lower()}@fsp.example",
                       "region": "Москва", "achievements": _achievements(random.Random(fsp_id), k, s, pref), "demo": True}
    for i in range(10, 410):
        fsp_id = f"FSP-{100000 + i}"
        first, last = rng.choice(FIRST), rng.choice(LAST_M)
        k = rng.choices([0, 1, 2, 3, 4, 5], weights=[12, 30, 25, 16, 10, 7])[0]
        out[fsp_id] = {"fsp_id": fsp_id, "full_name": f"{surname(first, last)} {first}", "email": f"{fsp_id.lower()}@fsp.example",
                       "region": rng.choice(REGIONS), "achievements": _achievements(rng, k, rng.random()), "demo": False}
    return out
