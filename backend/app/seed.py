"""Генератор демо-данных: `python -m app.seed` из папки backend/ (БД пересоздаётся).

Синтетические кандидаты проходят НАСТОЯЩИЙ движок тестирования: у каждого есть «истинный» уровень θ,
ответы моделируются по IRT 2PL, CAT подбирает вопросы, решение по грейду принимается теми же правилами,
что и для живых пользователей. Поэтому категории, θ и подтверждённые темы в демо получены честно.
Все компании, люди и мероприятия вымышлены.
"""
from __future__ import annotations

import argparse
import random
from datetime import timedelta

import numpy as np
from sqlalchemy import select

from app.config import BASE_DIR, settings
from app.db import Base, SessionLocal, engine
from app.dictionaries import INDUSTRY_CODES, SOFT_SKILL_CODES, SPEC_BY_CODE, grade_for_theta
from app.models import (Application, CandidateProfile, Company, GradeEvent, Invitation, Need, RegularTask,
                        SurveyResponse, TaskAssignment, TestAttempt, User, Vacancy, utcnow)
from app.security import hash_password
from app.services import irt, matching, tasks, testing, trust, webhooks
from app.services.bank import REGISTRY
from app.services.pdf import make_sample_resume
from fsp_mock.data import participants

DEMO_PASSWORD = "demo12345"

FIRST_M = ["Алексей", "Дмитрий", "Иван", "Сергей", "Никита", "Артём", "Михаил", "Кирилл", "Егор", "Максим", "Тимур",
           "Роман", "Павел", "Глеб", "Андрей", "Илья", "Денис", "Фёдор", "Лев", "Матвей"]
FIRST_F = ["Мария", "Анна", "Екатерина", "Ольга", "Полина", "Дарья", "Софья", "Алина", "Виктория", "Ксения",
           "Вероника", "Елизавета", "Арина", "Юлия", "Ирина", "Надежда"]
LAST = ["Иванов", "Смирнов", "Кузнецов", "Попов", "Васильев", "Петров", "Соколов", "Михайлов", "Новиков", "Фёдоров",
        "Морозов", "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов", "Козлов", "Степанов", "Николаев",
        "Орлов", "Андреев", "Макаров", "Никитин", "Захаров", "Зайцев", "Соловьёв", "Борисов", "Яковлев", "Григорьев"]
CITIES = ["Москва"] * 6 + ["Санкт-Петербург"] * 3 + ["Казань", "Новосибирск", "Екатеринбург", "Нижний Новгород", "Томск",
                                                     "Самара", "Краснодар", "Пермь", "Иннополис", "Воронеж", "Уфа"]
SPEC_WEIGHTS = {"backend": 30, "frontend": 22, "data": 18, "devops": 15, "qa": 15}
CORE_STACK = {
    "backend": ["python", "sql", "postgresql", "docker", "git", "rest", "http", "redis", "linux"],
    "frontend": ["javascript", "typescript", "react", "html", "css", "git", "rest", "webpack"],
    "data": ["python", "sql", "pandas", "numpy", "statistics", "ml", "scikit_learn", "git"],
    "devops": ["linux", "docker", "kubernetes", "ci_cd", "bash", "monitoring", "git", "terraform"],
    "qa": ["test_design", "manual_testing", "api_testing", "postman", "sql", "http", "python", "git"],
}
ABOUT = {
    "backend": ["Разрабатываю серверную часть и API, слежу за производительностью запросов к базе.",
                "Пишу микросервисы, люблю понятные контракты и тесты. Интересны высоконагруженные системы.",
                "Занимаюсь интеграциями и платёжными сценариями, внимательно отношусь к надёжности.",
                "Проектирую схемы данных и асинхронную обработку событий через очереди."],
    "frontend": ["Делаю интерфейсы на React, слежу за доступностью и скоростью загрузки.",
                 "Люблю аккуратную вёрстку и дизайн-системы, работаю в паре с дизайнерами.",
                 "Пишу SPA с упором на типизацию и тесты компонентов."],
    "data": ["Строю модели и провожу эксперименты, умею объяснять результаты бизнесу.",
             "Занимаюсь аналитикой продукта и A/B-тестами, пишу сложный SQL.",
             "Обучаю модели компьютерного зрения и NLP, довожу их до продакшена."],
    "devops": ["Поддерживаю Kubernetes-кластеры и CI/CD, автоматизирую всё, что повторяется.",
               "Настраиваю мониторинг и алертинг, разбираю инциденты и пишу постмортемы.",
               "Описываю инфраструктуру кодом на Terraform и Ansible."],
    "qa": ["Тестирую веб и API, пишу автотесты на pytest, проектирую тест-кейсы.",
           "Внимательно отношусь к требованиям, нахожу граничные случаи до релиза.",
           "Строю регресс на Playwright и интегрирую его в CI."],
}
SALARY = {"intern": (40_000, 75_000), "junior": (80_000, 150_000), "middle": (160_000, 290_000), "senior": (280_000, 460_000)}
YEARS = {"intern": (0, 0.5), "junior": (0.5, 1.5), "middle": (1.5, 4), "senior": (4, 10)}

COMPANIES = [
    {"email": "employer@demo.ru", "name": "Цифровые Решения Плюс", "industry": "fintech", "city": "Москва", "size": "200–500",
     "description": "Финтех-компания: платёжный шлюз и сервисы для малого бизнеса. Команды по 5–8 человек, продуктовый подход.",
     "website": "https://example.com/dsp", "contact_telegram": "@dsp_hiring"},
    {"email": "hr.logistics@demo.ru", "name": "Логистика Онлайн", "industry": "logistics", "city": "Москва", "size": "500–1000",
     "description": "Платформа маршрутизации доставки: миллионы событий в сутки, оптимизация маршрутов.", "contact_telegram": "@lo_hr"},
    {"email": "hr.gamelab@demo.ru", "name": "ГеймЛаб Студио", "industry": "gamedev", "city": "Санкт-Петербург", "size": "50–200",
     "description": "Студия мобильных и браузерных игр.", "contact_telegram": "@gamelab_jobs"},
    {"email": "hr.medtech@demo.ru", "name": "МедТех Системс", "industry": "healthtech", "city": "Санкт-Петербург", "size": "50–200",
     "description": "ML-сервисы для поддержки врачебных решений.", "contact_telegram": "@medtech_hr"},
    {"email": "hr.cloud@demo.ru", "name": "Облачная Платформа", "industry": "saas", "city": "Новосибирск", "size": "200–500",
     "description": "B2B-облако: managed Kubernetes, базы данных как сервис.", "contact_telegram": "@cloudplatform_hr"},
    {"email": "hr.smartcity@demo.ru", "name": "Умный город Лаб", "industry": "govtech", "city": "Казань", "size": "50–200",
     "description": "Цифровые сервисы для городской среды и транспорта.", "contact_telegram": "@smartcity_lab", "verified": False},
]

VACANCIES = [
    (0, "Python-разработчик в команду платежей", "backend", "middle", ["python", "fastapi", "postgresql", "kafka", "docker", "redis"],
     ["remote", "hybrid"], "Москва", 220_000, 320_000,
     "Развиваем платёжный шлюз: приём платежей, возвраты, сверки. Python 3.12, FastAPI, PostgreSQL, Kafka, Redis, Docker. "
     "Нужен опыт проектирования API и работы с транзакциями. Будет плюсом опыт с Kubernetes."),
    (0, "Frontend-разработчик (React)", "frontend", "junior", ["javascript", "typescript", "react", "css", "html", "rest"],
     ["hybrid"], "Москва", 120_000, 170_000,
     "Личный кабинет предпринимателя: React, TypeScript, дизайн-система. Ищем junior+ с пет-проектами или опытом до 1,5 лет."),
    (1, "Senior backend-разработчик (Go/Python): маршрутизация", "backend", "senior",
     ["go", "python", "postgresql", "kafka", "kubernetes", "system_design"], ["remote"], "", 350_000, 480_000,
     "Сервис расчёта маршрутов в реальном времени. Высокая нагрузка, событийная архитектура, Kafka, PostgreSQL. "
     "Ожидаем опыт проектирования распределённых систем и менторства."),
    (2, "QA-инженер (автотесты на Python)", "qa", "middle", ["pytest", "python", "api_testing", "test_design", "sql", "ci_cd"],
     ["remote"], "", 150_000, 220_000,
     "Автоматизация тестирования игрового бэкенда: pytest, тестирование API, интеграция в CI. Нужен опыт тест-дизайна."),
    (3, "Data Scientist: модели для диагностики", "data", "middle", ["python", "pandas", "scikit_learn", "pytorch", "statistics", "sql"],
     ["hybrid"], "Санкт-Петербург", 230_000, 330_000,
     "Модели классификации медицинских изображений и табличных данных. Python, pandas, scikit-learn, PyTorch, статистика."),
    (4, "DevOps-инженер", "devops", "middle", ["kubernetes", "docker", "terraform", "ci_cd", "monitoring", "linux", "helm"],
     ["remote"], "", 250_000, 350_000,
     "Эксплуатация managed Kubernetes, Terraform, GitLab CI, Prometheus и Grafana. Дежурства по графику."),
    (5, "Стажёр-аналитик данных", "data", "intern", ["python", "sql", "pandas", "statistics"], ["office"], "Казань", 50_000, 70_000,
     "Стажировка 3–6 месяцев с наставником: анализ данных городского транспорта, SQL, Python, pandas."),
    (4, "Junior QA (ручное тестирование)", "qa", "junior", ["manual_testing", "test_design", "postman", "sql", "http"],
     ["hybrid"], "Новосибирск", 80_000, 110_000,
     "Ручное тестирование веб-консоли облака: тест-кейсы, Postman, SQL. Обучим автотестам."),
]

TASKS = [
    (0, "Идемпотентность платёжного API", "backend", "approach", ["junior", "middle", "senior"],
     "Клиент отправляет запрос на списание, получает таймаут и повторяет запрос. Как спроектировать API и хранение, "
     "чтобы деньги гарантированно списались один раз? Опишите подход в 5–10 предложениях.",
     [{"point": "Ключ идемпотентности от клиента", "keywords": ["идемпотент", "idempotency", "ключ запроса", "request id"]},
      {"point": "Уникальное ограничение в БД", "keywords": ["уникальн", "unique", "constraint", "индекс"]},
      {"point": "Транзакции или блокировки", "keywords": ["транзакц", "блокировк", "for update", "lock"]},
      {"point": "Сохранение и возврат результата первой обработки", "keywords": ["сохран результат", "вернуть тот же", "кэшир ответ", "повторный ответ"]},
      {"point": "Статусы операции", "keywords": ["статус", "pending", "состояни"]}]),
    (1, "Кэш для расчёта маршрутов", "backend", "approach", ["middle", "senior"],
     "Расчёт маршрута занимает 2 секунды, запросы часто повторяются. Предложите схему кэширования. Что делать с "
     "инвалидацией и с одновременным промахом сотен запросов по одному ключу?",
     [{"point": "Ключ кэша и TTL", "keywords": ["ttl", "время жизни", "ключ кэша"]},
      {"point": "Инвалидация при изменении данных", "keywords": ["инвалидац", "сброс", "invalidate"]},
      {"point": "Защита от cache stampede", "keywords": ["stampede", "single flight", "блокировк", "lock", "одновременн"]},
      {"point": "Хранилище кэша", "keywords": ["redis", "memcached", "in-memory"]}]),
    (2, "Список из 10 000 элементов тормозит", "frontend", "solve", ["junior", "middle", "senior"],
     "В React-приложении список из 10 000 карточек с фильтром по вводу заметно тормозит. Как ускорить?",
     [{"point": "Виртуализация списка", "keywords": ["виртуализ", "react-window", "virtual"]},
      {"point": "Мемоизация", "keywords": ["memo", "usememo", "usecallback", "мемоиз"]},
      {"point": "Стабильные key", "keywords": ["key"]},
      {"point": "Debounce фильтра", "keywords": ["debounce", "дебаунс", "throttle", "задержк"]}]),
    (3, "Метрика для несбалансированной выборки", "data", "approach", ["junior", "middle", "senior"],
     "Положительный класс — 1% объектов. Какую метрику качества выбрать для модели и как подобрать порог?",
     [{"point": "Accuracy не подходит", "keywords": ["accuracy", "доля верных"]},
      {"point": "Precision/Recall/F1", "keywords": ["precision", "recall", "f1", "полнот", "точност"]},
      {"point": "PR-AUC или ROC-AUC", "keywords": ["pr-auc", "roc", "auc"]},
      {"point": "Стратификация и подбор порога", "keywords": ["стратиф", "порог", "threshold"]}]),
    (4, "Под в CrashLoopBackOff", "devops", "approach", ["junior", "middle", "senior"],
     "После деплоя под в Kubernetes перезапускается по кругу (CrashLoopBackOff). Опишите план диагностики.",
     [{"point": "Логи контейнера (в т.ч. предыдущего)", "keywords": ["logs", "лог", "--previous"]},
      {"point": "kubectl describe и события", "keywords": ["describe", "event", "событи"]},
      {"point": "Пробы liveness/readiness", "keywords": ["liveness", "readiness", "проб"]},
      {"point": "Лимиты и OOMKilled", "keywords": ["oom", "limit", "лимит", "памят"]},
      {"point": "Конфигурация и секреты", "keywords": ["configmap", "secret", "переменн", "конфиг"]}]),
    (2, "Тест-кейсы для поля «возраст»", "qa", "solve", ["intern", "junior", "middle"],
     "Поле «Возраст» принимает целые числа от 18 до 65 включительно. Составьте минимальный набор проверок.",
     [{"point": "Граничные значения 17/18 и 65/66", "keywords": ["17", "66", "границ"]},
      {"point": "Классы эквивалентности", "keywords": ["эквивалент", "класс"]},
      {"point": "Нечисловой и пустой ввод", "keywords": ["букв", "пуст", "символ", "текст"]},
      {"point": "Дробные и отрицательные", "keywords": ["дробн", "отрицат", "-1", "18.5"]}]),
]

NEEDS = [
    {"title": "Бэкенд платёжного шлюза", "specialization": "backend", "grade": "middle",
     "stack_must": ["python", "postgresql", "kafka", "docker"], "stack_nice": ["redis", "kubernetes"],
     "work_format": ["remote", "hybrid"], "city": "Москва", "salary_from": 250_000, "salary_to": 330_000,
     "description": "Нужен Middle Python-разработчик в команду платежей: приём платежей, возвраты, сверки с банками. "
                    "PostgreSQL, Kafka, Docker обязательно. Будет плюсом Redis и Kubernetes.",
     "team_about": "Команда из 6 человек: 4 бэкенда, QA, продакт. Релизы два раза в неделю."},
    {"title": "Аналитик-исследователь антифрода", "specialization": "data", "grade": "middle",
     "stack_must": ["python", "sql", "statistics", "scikit_learn"], "stack_nice": ["ab_testing", "airflow"],
     "work_format": ["hybrid"], "city": "Москва", "salary_from": 220_000, "salary_to": 300_000,
     "description": "Модели выявления мошеннических операций и эксперименты с правилами. Python, SQL, статистика, scikit-learn.",
     "team_about": "Отдел риск-аналитики, 5 человек."},
]


def _name(rng: random.Random) -> str:
    if rng.random() < 0.38:
        return f"{rng.choice(LAST)}а {rng.choice(FIRST_F)}"
    return f"{rng.choice(LAST)} {rng.choice(FIRST_M)}"


def _stack(rng: random.Random, spec: str, grade: str) -> list[str]:
    core = CORE_STACK[spec]
    extra = [s for s in SPEC_BY_CODE[spec]["skills"] if s not in core]
    k_core = {"intern": 3, "junior": 4, "middle": 5, "senior": 6}[grade] + rng.randint(0, 2)
    k_extra = {"intern": 0, "junior": 1, "middle": 2, "senior": 3}[grade] + rng.randint(0, 2)
    return rng.sample(core, min(k_core, len(core))) + rng.sample(extra, min(k_extra, len(extra)))


def simulate_attempt(db, cand: CandidateProfile, grade: str, theta_true: float, rng: random.Random,
                     nrng: np.random.Generator, deterministic: bool = False) -> TestAttempt:
    """Проходит тест через движок, отвечая как кандидат с уровнем theta_true (модель 2PL).
    deterministic=True — «идеальный» отвечающий (верно, если сложность шаблона ниже уровня): для стабильного демо."""
    att = testing.start_attempt(db, cand, grade, rng)
    while att.status == "in_progress":
        item = testing.current_item(att)
        t = REGISTRY[item.template_id]
        correct = t.b < theta_true if deterministic else irt.simulate_answer(theta_true, t.a, t.b, nrng)
        wrong = [i for i in range(len(item.payload["options"])) if i != item.correct_index]
        idx = item.correct_index if correct else rng.choice(wrong)
        testing.submit_answer(db, att, item.id, idx, rng, now=item.served_at + timedelta(seconds=rng.randint(15, 100)))
    return att


def shift_history(db, cand: CandidateProfile, days: float) -> None:
    """Сдвигает историю кандидата в прошлое, чтобы демо выглядело как живая база."""
    d = timedelta(days=days)
    for att in db.execute(select(TestAttempt).where(TestAttempt.candidate_id == cand.id)).scalars():
        att.started_at -= d
        att.finished_at = att.finished_at - d if att.finished_at else None
        for it in att.items:
            it.served_at -= d
            it.answered_at = it.answered_at - d if it.answered_at else None
    for ev in db.execute(select(GradeEvent).where(GradeEvent.candidate_id == cand.id)).scalars():
        ev.created_at -= d
    for s in db.execute(select(SurveyResponse).where(SurveyResponse.candidate_id == cand.id)).scalars():
        s.created_at -= d
    if cand.grade_changed_at:
        cand.grade_changed_at -= d


def make_candidate(db, rng, nrng, pwd_hash: str, idx: int, spec: str, theta_true: float, *, email: str | None = None,
                   name: str | None = None, fsp: dict | None = None, publish: bool = True, overrides: dict | None = None,
                   upgrade_prob: float = 0.6, deterministic: bool = False):
    user = User(email=email or f"cand{idx:04d}@demo.ru", password_hash=pwd_hash, role="candidate", email_verified=True,
                consent_pd_at=utcnow())
    db.add(user)
    db.flush()
    # Самооценка грейда: истинный уровень + шум (люди склонны переоценивать себя)
    self_theta = theta_true + rng.gauss(0.25, 0.5)
    declared = grade_for_theta(self_theta) or "intern"
    lo, hi = YEARS[declared]
    smin, smax = SALARY[declared]
    cand = CandidateProfile(
        user_id=user.id, anon_code=f"К-{1000 + idx}", full_name=name or _name(rng), phone=f"+79{rng.randint(10**8, 10**9 - 1)}",
        telegram=f"@dev_{idx:04d}", contact_email=user.email, city=rng.choice(CITIES), relocation=rng.random() < 0.3,
        about=rng.choice(ABOUT[spec]), experience_years=round(rng.uniform(lo, hi), 1),
        roles=["developer"] + (["mentor"] if declared == "senior" and rng.random() < 0.5 else [])
        + (["team_lead"] if declared == "senior" and rng.random() < 0.3 else []),
        soft_skills=rng.sample(SOFT_SKILL_CODES, rng.randint(2, 4)), industries=rng.sample(INDUSTRY_CODES, rng.randint(1, 3)),
        specialization=spec, stack=_stack(rng, spec, declared),
        work_format=rng.choice([["remote"], ["remote", "hybrid"], ["hybrid"], ["office", "hybrid"], ["office"]]),
        salary_expect_min=int(round(rng.uniform(smin, smax), -4)),
        job_status=rng.choices(["active", "open", "closed"], weights=[60, 32, 8])[0],
        consent_publish_at=utcnow() if publish else None,
        privacy={"show_name": rng.random() < 0.2, "show_salary": rng.random() < 0.9, "show_fsp": True, "show_tasks": True,
                 "hidden_companies": []},
        onboarding_done=True,
    )
    if overrides:
        for k, v in overrides.items():
            if not k.startswith("_"):
                setattr(cand, k, v)
        declared = overrides.get("_declared", declared)
    if fsp:
        cand.fsp_id, cand.fsp_linked_at = fsp["fsp_id"], utcnow()
        cand.fsp_achievements, cand.fsp_fetched_at = fsp["achievements"], utcnow()
    db.add(cand)
    db.flush()
    db.add(SurveyResponse(candidate_id=cand.id, answers={
        "industries": cand.industries, "specialization": spec, "stack": cand.stack, "experience_years": cand.experience_years,
        "work_format": cand.work_format, "salary_expect_min": cand.salary_expect_min, "city": cand.city,
        "relocation": cand.relocation, "declared_grade": declared}))
    db.commit()
    att = simulate_attempt(db, cand, declared, theta_true, rng, nrng, deterministic)
    if att.result == "not_confirmed" and att.suggested_grade:
        simulate_attempt(db, cand, att.suggested_grade, theta_true, rng, nrng, deterministic)
    elif att.result == "confirmed_plus" and rng.random() < upgrade_prob:
        testing.accept_upgrade(db, cand, att)
    return cand


def run(n_candidates: int = 320, seed: int = 7) -> None:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    pwd_hash = hash_password(DEMO_PASSWORD)

    companies = []
    for c in COMPANIES:
        u = User(email=c["email"], password_hash=pwd_hash, role="employer", email_verified=True, consent_pd_at=utcnow())
        db.add(u)
        db.flush()
        slug = c["email"].split("@")[0].replace("hr.", "") if c["email"].startswith("hr.") else "dsp"
        comp = Company(user_id=u.id, name=c["name"], industry=c["industry"], city=c["city"], size=c["size"],
                       description=c["description"], website=f"https://{slug}.example", contact_email=f"hr@{slug}.example",
                       contact_telegram=c.get("contact_telegram", ""), invite_quota_week=settings.invite_quota_week)
        if c.get("verified", True):  # «Умный город Лаб» оставлен неподтверждённым — видно сниженную квоту
            comp.inn = trust.make_inn(f"77{rng.randrange(10**7):07d}")
            trust.verify(comp)
        db.add(comp)
        companies.append(comp)
    db.flush()

    vacancies = []
    for ci, title, spec, grade, stack, fmt, city, sf, st, desc in VACANCIES:
        v = Vacancy(company_id=companies[ci].id, title=title, description=desc, specialization=spec, grade=grade, stack=stack,
                    work_format=fmt, city=city, salary_from=sf, salary_to=st, status="published",
                    created_at=utcnow() - timedelta(days=rng.randint(1, 25)))
        db.add(v)
        vacancies.append(v)
    task_objs = []
    for ci, title, spec, kind, grades, body, rubric in TASKS:
        t = RegularTask(company_id=companies[ci].id, title=title, body=body, kind=kind, specialization=spec, grades=grades,
                        rubric=rubric, created_at=utcnow() - timedelta(days=rng.randint(20, 60)))
        db.add(t)
        task_objs.append(t)
    db.commit()

    # --- кандидаты
    fsp_pool = [p for fid, p in participants().items() if not p.get("demo")]
    rng.shuffle(fsp_pool)
    specs = list(SPEC_WEIGHTS)
    weights = list(SPEC_WEIGHTS.values())
    cands: list[CandidateProfile] = []
    print(f"Генерация {n_candidates} кандидатов через движок тестирования…")
    for i in range(1, n_candidates + 1):
        spec = rng.choices(specs, weights=weights)[0]
        theta = float(np.clip(nrng.normal(0.15, 1.0), -2.8, 2.9))
        fsp = None
        if rng.random() < 0.42 and fsp_pool:
            fsp = fsp_pool.pop()
            # Участники соревнований в среднем сильнее — небольшая корреляция уровня с достижениями
            theta = float(np.clip(theta + 0.15 * len(fsp["achievements"]), -2.8, 2.9))
        c = make_candidate(db, rng, nrng, pwd_hash, i, spec, theta, fsp=fsp, publish=rng.random() < 0.93)
        shift_history(db, c, rng.uniform(5, 200))
        db.commit()
        cands.append(c)
        if i % 50 == 0:
            print(f"  {i}/{n_candidates}")

    # --- демо-кандидат
    demo_fsp = participants()["FSP-100004"]
    demo = make_candidate(db, rng, nrng, pwd_hash, 0, "backend", 1.05, email="candidate@demo.ru", name="Орлова Дарья",
                          fsp=demo_fsp, overrides={
                              "_declared": "middle", "city": "Москва", "relocation": False, "experience_years": 3.5,
                              "stack": ["python", "fastapi", "postgresql", "redis", "docker", "kafka", "git", "rest"],
                              "work_format": ["remote", "hybrid"], "salary_expect_min": 260_000, "job_status": "active",
                              "about": "Python-разработчик, 3,5 года в финтехе: платежи, очереди, PostgreSQL. Капитан команды "
                                       "на чемпионате по продуктовому программированию.",
                              "roles": ["developer", "captain"], "soft_skills": ["teamwork", "responsibility", "leadership"],
                              "industries": ["fintech", "saas"], "telegram": "@daria_orlova_dev", "phone": "+79161234567",
                              "privacy": {"show_name": False, "show_salary": True, "show_fsp": True, "show_tasks": True,
                                          "hidden_companies": []}}, upgrade_prob=0.0, deterministic=True)
    shift_history(db, demo, 40)
    db.commit()
    cands.append(demo)
    visible = [c for c in cands if c.grade and c.consent_publish_at and c.job_status != "closed"]
    others = [c for c in visible if c.id != demo.id]  # демо-кандидату активность задаём явно ниже

    # --- регулярные задания: часть кандидатов уже решала
    answers = {
        "backend": "Клиент передаёт ключ идемпотентности в заголовке, на сервере уникальный индекс по ключу, операция "
                   "выполняется в транзакции, результат сохраняем и при повторе возвращаем тот же ответ. Статусы pending/done.",
        "frontend": "Виртуализация списка через react-window, мемоизация карточек через memo, стабильный key, debounce на фильтр.",
        "data": "Accuracy не подходит. Смотрю precision и recall, PR-AUC, порог подбираю на стратифицированной валидации.",
        "devops": "Смотрю kubectl logs --previous, describe и события, проверяю liveness/readiness пробы, лимиты памяти на OOMKilled, configmap и секреты.",
        "qa": "Граничные значения 17, 18, 65, 66; классы эквивалентности; пустое поле, буквы, дробные 18.5 и отрицательные -1.",
    }
    for c in rng.sample(others, k=min(110, len(others))):
        a = tasks.assign_next(db, c)
        if a is None:
            continue
        full = answers[c.specialization]
        words = full.split()
        text = " ".join(words[: rng.randint(max(6, len(words) // 3), len(words))])
        a.answer = text
        a.auto_score, a.rubric_hits = tasks.score_answer(text, a.task.rubric)
        a.status = "submitted"
        a.assigned_at = utcnow() - timedelta(days=rng.randint(8, 80))
        a.submitted_at = a.assigned_at + timedelta(days=rng.randint(0, 3))
        if rng.random() < 0.4:
            a.employer_score = rng.randint(2, 5)
        db.commit()

    # --- приглашения в разных статусах
    statuses = ["sent", "viewed", "accepted", "declined", "accepted", "viewed", "declined", "expired"]
    reasons = ["salary", "stack", "format", "not_looking", "company"]
    for comp in companies[1:]:
        for c in rng.sample(others, k=min(6, len(others))):
            st = rng.choice(statuses)
            created = utcnow() - timedelta(days=rng.randint(1, 12) if st != "expired" else rng.randint(16, 30))
            sal_from = int(round((c.salary_expect_min or 150_000) * rng.uniform(0.85, 1.05), -4))
            inv = Invitation(company_id=comp.id, candidate_id=c.id, title=f"{SPEC_BY_CODE[c.specialization]['short']}-специалист",
                             description=f"{comp.description} Приглашаем обсудить роль в команде.",
                             salary_from=sal_from, salary_to=int(round(sal_from * 1.25, -4)), work_format=c.work_format,
                             contact_method=f"Telegram {comp.contact_telegram}", status=st, created_at=created,
                             expires_at=created + timedelta(days=settings.invite_ttl_days),
                             below_expectations=bool(c.salary_expect_min and sal_from * 1.25 < c.salary_expect_min))
            if st != "sent":
                inv.viewed_at = created + timedelta(hours=rng.randint(1, 30))
            if st in ("accepted", "declined"):
                inv.responded_at = inv.viewed_at + timedelta(hours=rng.randint(1, 48))
            if st == "declined":
                inv.decline_reason = rng.choice(reasons)
                if inv.decline_reason == "salary":
                    inv.expected_salary = int(round(inv.salary_to * 1.2, -4))
            db.add(inv)
    db.commit()

    # --- отклики на вакансии
    for v in vacancies:
        pool = [c for c in others if c.specialization == v.specialization]
        for c in rng.sample(pool, k=min(len(pool), rng.randint(2, 6))):
            st = matching.strength(c, [])
            m = matching.match(matching.NeedSpec.from_vacancy(v), c, st)
            db.add(Application(vacancy_id=v.id, candidate_id=c.id, cover_letter="Здравствуйте! Интересна ваша вакансия, готов обсудить детали.",
                               match_score=m["score"] if m else None, status=rng.choice(["sent", "viewed", "invited", "rejected", "sent"]),
                               created_at=utcnow() - timedelta(days=rng.randint(0, 14))))
    db.commit()

    # --- демо-работодатель: потребности, подборки, приглашения
    main = companies[0]
    needs = []
    for n in NEEDS:
        need = Need(company_id=main.id, **n)
        db.add(need)
        db.commit()
        matching.build_selection(db, need, main)
        needs.append(need)
    sel = matching.rank_for_need(db, matching.NeedSpec.from_need(needs[0]), main)
    top = [c for c, _m, _s in sel if c.id != demo.id][:8]
    for c, st in zip(top[:5], ["accepted", "declined", "viewed", "sent", "accepted"]):
        created = utcnow() - timedelta(days=rng.randint(1, 6))
        inv = Invitation(company_id=main.id, candidate_id=c.id, need_id=needs[0].id, title="Python-разработчик (платежи)",
                         description="Платёжный шлюз: приём платежей, возвраты, сверки. Команда из 6 человек, релизы два раза в неделю.",
                         salary_from=260_000, salary_to=320_000, work_format=["remote", "hybrid"],
                         contact_method="Telegram @dsp_hiring или hr@dsp.example", status=st, created_at=created,
                         expires_at=created + timedelta(days=settings.invite_ttl_days),
                         below_expectations=bool(c.salary_expect_min and 320_000 < c.salary_expect_min))
        if st != "sent":
            inv.viewed_at = created + timedelta(hours=3)
        if st in ("accepted", "declined"):
            inv.responded_at = created + timedelta(hours=20)
        if st == "declined":
            inv.decline_reason, inv.expected_salary, inv.decline_comment = "salary", 360_000, "Интересно, но рассматриваю от 360 тысяч."
        db.add(inv)
    for si in db.execute(select(matching.SelectionItem).where(matching.SelectionItem.need_id == needs[0].id)
                         .order_by(matching.SelectionItem.rank)).scalars().all()[:3]:
        si.pinned = True

    # --- демо-кандидату: входящие приглашения, отклик и задания
    for ci, st, title, sf, stt in [(1, "sent", "Backend-разработчик (Python), маршрутизация", 270_000, 340_000),
                                   (4, "viewed", "Python-разработчик в команду managed-баз данных", 240_000, 300_000),
                                   (5, "declined", "Разработчик сервисов городского транспорта", 180_000, 230_000)]:
        comp = companies[ci]
        created = utcnow() - timedelta(days=rng.randint(1, 5))
        inv = Invitation(company_id=comp.id, candidate_id=demo.id, title=title,
                         description=f"{comp.description} Увидели ваш подтверждённый профиль и результаты ФСП — хотим познакомиться.",
                         salary_from=sf, salary_to=stt, work_format=["remote", "hybrid"], contact_method=f"Telegram {comp.contact_telegram}",
                         status=st, created_at=created, expires_at=created + timedelta(days=settings.invite_ttl_days),
                         below_expectations=stt < (demo.salary_expect_min or 0))
        if st != "sent":
            inv.viewed_at = created + timedelta(hours=2)
        if st == "declined":
            inv.responded_at, inv.decline_reason, inv.expected_salary = created + timedelta(hours=5), "salary", 270_000
        db.add(inv)
    m = matching.match(matching.NeedSpec.from_vacancy(vacancies[0]), demo, matching.strength(demo, []))
    db.add(Application(vacancy_id=vacancies[0].id, candidate_id=demo.id, status="viewed",
                       cover_letter="Работаю с платежами 3 года, хочу развиваться в вашей команде.",
                       match_score=m["score"] if m else None, created_at=utcnow() - timedelta(days=2)))
    # Решённое задание 10 дней назад: следующее уже доступно по кнопке «Получить задание»
    a = TaskAssignment(task_id=task_objs[0].id, candidate_id=demo.id, status="submitted", answer=answers["backend"],
                       assigned_at=utcnow() - timedelta(days=10), submitted_at=utcnow() - timedelta(days=9), employer_score=5)
    a.auto_score, a.rubric_hits = tasks.score_answer(a.answer, task_objs[0].rubric)
    db.add(a)
    db.commit()

    # Интеграция с ATS у демо-работодателя: события уходят во встроенный демо-приёмник
    main.webhook_url, main.webhook_secret = settings.demo_webhook_url, webhooks.new_secret()
    # Одна жалоба кандидата на «Логистику Онлайн» — видно сигнал доверия в приглашении
    complained = db.execute(select(Invitation).where(Invitation.company_id == companies[1].id,
                                                    Invitation.status == "declined")).scalars().first()
    if complained:
        complained.complaint_reason, complained.complaint_at = "conditions", utcnow() - timedelta(days=2)
        complained.complaint_comment = "На созвоне вилка оказалась на 30% ниже, чем в приглашении."
    db.commit()

    sample = BASE_DIR.parent / "docs" / "samples" / "resume_sample.pdf"
    make_sample_resume(sample)
    print("Готово.")
    print(f"  демо-кандидат: {demo.full_name}, категория {demo.grade} (θ={demo.theta:.2f}), ФСП {demo.fsp_id}")
    db.close()
    print(f"  кандидатов: {len(cands)}, видимых работодателям: {len(visible)}")
    print(f"  демо-кандидат: candidate@demo.ru / {DEMO_PASSWORD}")
    print(f"  демо-работодатель: employer@demo.ru / {DEMO_PASSWORD}")
    print(f"  пример резюме для распознавания: {sample.relative_to(BASE_DIR.parent)}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Пересоздать БД и наполнить демо-данными")
    ap.add_argument("--candidates", type=int, default=320)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()
    run(args.candidates, args.seed)
