"""Справочники платформы: специализации, грейды, навыки (с синонимами для NLP), отрасли, софт-скиллы.

Справочник составлен командой по общепринятым в ИТ понятиям (см. ТЗ, п. 2). Навыки имеют канонический
идентификатор — он же используется как «тема» шаблонов заданий, поэтому навык, проверенный тестом,
однозначно сопоставляется со стеком в потребности работодателя.
"""

# --- Грейды и пороги на шкале θ (IRT). Порог — минимальная θ, при которой грейд считается подтверждённым.
GRADES: list[dict] = [
    {"code": "intern", "label": "Стажёр", "cutoff": -1.6, "years": "до 0,5 года",
     "description": "Учебные и пет-проекты, коммерческого опыта до полугода. Решаю задачи с подробной постановкой."},
    {"code": "junior", "label": "Junior", "cutoff": -0.6, "years": "до 1,5 лет",
     "description": "Решаю типовые задачи самостоятельно, сложные — с ревью и подсказками старших коллег."},
    {"code": "middle", "label": "Middle", "cutoff": 0.4, "years": "1,5–4 года",
     "description": "Самостоятельно веду задачи от постановки до продакшена, оцениваю сроки, ревьюю код коллег."},
    {"code": "senior", "label": "Senior", "cutoff": 1.4, "years": "4+ лет",
     "description": "Проектирую решения, отвечаю за качество и надёжность, развиваю команду и процессы."},
]
GRADE_CODES = [g["code"] for g in GRADES]
GRADE_BY_CODE = {g["code"]: g for g in GRADES}
THETA_MAX = 2.4  # верхняя граница полосы старшего грейда, используется при расчёте T


def grade_index(code: str) -> int:
    return GRADE_CODES.index(code)


def grade_cutoff(code: str) -> float:
    return GRADE_BY_CODE[code]["cutoff"]


def grade_upper(code: str) -> float:
    i = grade_index(code)
    return GRADES[i + 1]["cutoff"] if i + 1 < len(GRADES) else THETA_MAX


def grade_for_theta(theta: float) -> str | None:
    """Максимальный грейд, порог которого не выше θ."""
    best = None
    for g in GRADES:
        if theta >= g["cutoff"]:
            best = g["code"]
    return best


# --- Навыки: канонический id → подпись и регулярные выражения синонимов (регистр игнорируется,
# фрагмент вида (?-i:...) чувствителен к регистру).
SKILLS: dict[str, dict] = {
    # Языки
    "python": {"label": "Python", "re": [r"python", r"питон", r"пайтон"]},
    "java": {"label": "Java", "re": [r"\bjava\b", r"джава"]},
    "go": {"label": "Go", "re": [r"golang", r"(?-i:\bGo\b)"]},
    "csharp": {"label": "C#", "re": [r"c#", r"\bc sharp\b"]},
    "cpp": {"label": "C++", "re": [r"c\+\+", r"\bcpp\b"]},
    "javascript": {"label": "JavaScript", "re": [r"javascript", r"(?<![.\w])js\b", r"ecmascript", r"\bes6\b"]},
    "typescript": {"label": "TypeScript", "re": [r"typescript", r"\bts\b"]},
    "kotlin": {"label": "Kotlin", "re": [r"kotlin", r"котлин"]},
    "php": {"label": "PHP", "re": [r"\bphp\b"]},
    "rust": {"label": "Rust", "re": [r"\brust\b"]},
    "sql": {"label": "SQL", "re": [r"\bsql\b", r"t-sql", r"pl/sql", r"plpgsql"]},
    "bash": {"label": "Bash/Shell", "re": [r"\bbash\b", r"\bshell\b", r"\bsh-скрипт\w*"]},
    # Бэкенд-фреймворки и платформы
    "nodejs": {"label": "Node.js", "re": [r"node\.?js", r"\bnode\b"]},
    "django": {"label": "Django", "re": [r"django"]},
    "fastapi": {"label": "FastAPI", "re": [r"fastapi"]},
    "flask": {"label": "Flask", "re": [r"\bflask\b"]},
    "spring": {"label": "Spring", "re": [r"\bspring\b", r"spring boot"]},
    "dotnet": {"label": ".NET", "re": [r"\.net\b", r"dotnet", r"asp\.net"]},
    "nestjs": {"label": "NestJS", "re": [r"nest\.?js"]},
    # Хранилища и очереди
    "postgresql": {"label": "PostgreSQL", "re": [r"postgre\w*", r"постгре\w*", r"\bpg\b", r"pgsql"]},
    "mysql": {"label": "MySQL", "re": [r"mysql", r"mariadb"]},
    "mongodb": {"label": "MongoDB", "re": [r"mongo\w*"]},
    "redis": {"label": "Redis", "re": [r"redis"]},
    "clickhouse": {"label": "ClickHouse", "re": [r"clickhouse", r"кликхаус"]},
    "elasticsearch": {"label": "Elasticsearch", "re": [r"elastic\w*", r"opensearch"]},
    "kafka": {"label": "Kafka", "re": [r"kafka", r"кафк\w*"]},
    "rabbitmq": {"label": "RabbitMQ", "re": [r"rabbit\w*", r"\bamqp\b"]},
    # Протоколы и архитектура
    "http": {"label": "HTTP", "re": [r"\bhttps?\b"]},
    "rest": {"label": "REST API", "re": [r"(?-i:\bREST\b)", r"restful", r"\brest api\b", r"\brest-api\b"]},
    "grpc": {"label": "gRPC", "re": [r"grpc", r"protobuf"]},
    "graphql": {"label": "GraphQL", "re": [r"graphql"]},
    "microservices": {"label": "Микросервисы", "re": [r"микросервис\w*", r"microservices?"]},
    "system_design": {"label": "System design", "re": [r"system design", r"архитектур\w* (систем|приложени|сервис)\w*", r"проектировани\w* (систем|сервис|архитектур)\w*", r"высоконагруж\w*"]},
    "design_patterns": {"label": "Паттерны, SOLID", "re": [r"паттерн\w*", r"шаблон\w* проектирования", r"design patterns?", r"\bsolid\b"]},
    "oop": {"label": "ООП", "re": [r"\bооп\b", r"\boop\b", r"объектно-ориентирован\w*"]},
    "algorithms": {"label": "Алгоритмы", "re": [r"алгоритм\w*", r"algorithms?"]},
    "data_structures": {"label": "Структуры данных", "re": [r"структур\w* данных", r"data structures?"]},
    "git": {"label": "Git", "re": [r"\bgit\b", r"github", r"gitlab", r"bitbucket"]},
    "concurrency": {"label": "Конкурентность", "re": [r"многопоточ\w*", r"асинхрон\w*", r"concurren\w*", r"asyncio", r"async/await", r"параллельн\w*"]},
    # Фронтенд
    "html": {"label": "HTML", "re": [r"\bhtml5?\b", r"вёрстк\w*", r"верстк\w*"]},
    "css": {"label": "CSS", "re": [r"\bcss3?\b", r"\bscss\b", r"\bsass\b", r"flexbox", r"css grid"]},
    "react": {"label": "React", "re": [r"\breact(\.js|js)?\b", r"реакт"]},
    "vue": {"label": "Vue", "re": [r"\bvue(\.js)?\b", r"nuxt"]},
    "angular": {"label": "Angular", "re": [r"angular"]},
    "redux": {"label": "Redux/MobX", "re": [r"redux", r"mobx", r"zustand", r"effector"]},
    "nextjs": {"label": "Next.js", "re": [r"next\.?js"]},
    "webpack": {"label": "Webpack/Vite", "re": [r"webpack", r"\bvite\b", r"сборщик\w*"]},
    "browser": {"label": "Browser API, DOM", "re": [r"\bdom\b", r"event loop", r"браузер\w*", r"web api"]},
    "jest": {"label": "Jest/Vitest", "re": [r"\bjest\b", r"vitest", r"testing library"]},
    "a11y": {"label": "Доступность (a11y)", "re": [r"\ba11y\b", r"доступност\w* интерфейс\w*", r"accessibility", r"wcag"]},
    # Данные и ML
    "pandas": {"label": "pandas", "re": [r"pandas"]},
    "numpy": {"label": "NumPy", "re": [r"numpy"]},
    "scikit_learn": {"label": "scikit-learn", "re": [r"scikit-learn", r"sklearn", r"scikit learn"]},
    "pytorch": {"label": "PyTorch", "re": [r"pytorch", r"\btorch\b"]},
    "tensorflow": {"label": "TensorFlow", "re": [r"tensorflow", r"keras"]},
    "statistics": {"label": "Статистика", "re": [r"статистик\w*", r"statistics", r"теори\w* вероятност\w*", r"матстат\w*"]},
    "ml": {"label": "Машинное обучение", "re": [r"\bml\b", r"машинн\w* обучени\w*", r"machine learning"]},
    "deep_learning": {"label": "Deep learning", "re": [r"deep learning", r"глубок\w* обучени\w*", r"нейросет\w*", r"нейронн\w* сет\w*"]},
    "nlp": {"label": "NLP", "re": [r"\bnlp\b", r"обработк\w* естественн\w* язык\w*", r"\bllm\b"]},
    "cv": {"label": "Computer vision", "re": [r"computer vision", r"компьютерн\w* зрени\w*", r"opencv"]},
    "spark": {"label": "Spark/Hadoop", "re": [r"spark", r"hadoop"]},
    "airflow": {"label": "Airflow", "re": [r"airflow"]},
    "ab_testing": {"label": "A/B-тесты", "re": [r"a/b", r"\bаб-тест\w*", r"ab-тест\w*", r"\bab test\w*"]},
    "data_viz": {"label": "Визуализация данных", "re": [r"tableau", r"power bi", r"superset", r"matplotlib", r"seaborn", r"datalens", r"визуализаци\w* данных"]},
    # Инфраструктура
    "linux": {"label": "Linux", "re": [r"linux", r"линукс", r"\bunix\b", r"ubuntu", r"debian", r"centos"]},
    "docker": {"label": "Docker", "re": [r"docker", r"докер\w*", r"контейнеризаци\w*"]},
    "kubernetes": {"label": "Kubernetes", "re": [r"kubernetes", r"\bk8s\b", r"кубер\w*", r"openshift"]},
    "helm": {"label": "Helm", "re": [r"\bhelm\b"]},
    "terraform": {"label": "Terraform", "re": [r"terraform"]},
    "ansible": {"label": "Ansible", "re": [r"ansible"]},
    "ci_cd": {"label": "CI/CD", "re": [r"ci/cd", r"ci-cd", r"gitlab ci", r"github actions", r"jenkins", r"teamcity", r"argo ?cd"]},
    "monitoring": {"label": "Prometheus/Grafana", "re": [r"prometheus", r"grafana", r"мониторинг\w*", r"observability", r"zabbix"]},
    "nginx": {"label": "Nginx", "re": [r"nginx", r"haproxy"]},
    "cloud": {"label": "Облака", "re": [r"\baws\b", r"yandex cloud", r"\bgcp\b", r"azure", r"облачн\w*"]},
    "networking": {"label": "Сети (TCP/IP, DNS)", "re": [r"tcp/ip", r"\btcp\b", r"\bdns\b", r"сетев\w* протокол\w*", r"\bosi\b"]},
    # Тестирование
    "manual_testing": {"label": "Ручное тестирование", "re": [r"ручн\w* тестировани\w*", r"manual testing", r"manual qa"]},
    "test_design": {"label": "Тест-дизайн", "re": [r"тест-дизайн\w*", r"test design", r"тест-кейс\w*", r"чек-лист\w*", r"test cases?"]},
    "api_testing": {"label": "Тестирование API", "re": [r"тестировани\w* api", r"api testing", r"api-тест\w*"]},
    "postman": {"label": "Postman", "re": [r"postman"]},
    "selenium": {"label": "Selenium", "re": [r"selenium", r"selenide"]},
    "playwright": {"label": "Playwright", "re": [r"playwright"]},
    "cypress": {"label": "Cypress", "re": [r"cypress"]},
    "pytest": {"label": "pytest", "re": [r"pytest"]},
    "junit": {"label": "JUnit/TestNG", "re": [r"junit", r"testng"]},
    "load_testing": {"label": "Нагрузочное тестирование", "re": [r"нагрузочн\w*", r"load testing", r"jmeter", r"\bk6\b", r"locust", r"gatling"]},
    "allure": {"label": "Allure", "re": [r"allure"]},
}

# --- Специализации и релевантные им навыки (порядок = порядок показа в опросе)
SPECIALIZATIONS: list[dict] = [
    {"code": "backend", "label": "Backend-разработка", "short": "Backend",
     "description": "Серверная логика, API, базы данных, интеграции.",
     "skills": ["python", "java", "go", "csharp", "javascript", "typescript", "nodejs", "php", "kotlin", "cpp", "rust",
                "django", "fastapi", "flask", "spring", "dotnet", "nestjs", "sql", "postgresql", "mysql", "mongodb",
                "redis", "clickhouse", "kafka", "rabbitmq", "elasticsearch", "http", "rest", "grpc", "graphql",
                "microservices", "concurrency", "system_design", "design_patterns", "oop", "docker", "kubernetes",
                "linux", "git", "algorithms", "data_structures"]},
    {"code": "frontend", "label": "Frontend-разработка", "short": "Frontend",
     "description": "Веб-интерфейсы, клиентская логика, вёрстка и производительность в браузере.",
     "skills": ["javascript", "typescript", "html", "css", "react", "vue", "angular", "redux", "nextjs", "webpack",
                "browser", "http", "rest", "graphql", "jest", "playwright", "a11y", "nodejs", "git", "algorithms",
                "data_structures", "design_patterns"]},
    {"code": "data", "label": "Data Science / ML", "short": "Data/ML",
     "description": "Анализ данных, машинное обучение, модели и эксперименты.",
     "skills": ["python", "sql", "postgresql", "clickhouse", "pandas", "numpy", "scikit_learn", "pytorch",
                "tensorflow", "statistics", "ml", "deep_learning", "nlp", "cv", "spark", "airflow", "ab_testing",
                "data_viz", "docker", "git", "linux", "algorithms"]},
    {"code": "devops", "label": "DevOps / SRE", "short": "DevOps",
     "description": "Инфраструктура, CI/CD, контейнеры, надёжность и наблюдаемость.",
     "skills": ["linux", "bash", "docker", "kubernetes", "helm", "terraform", "ansible", "ci_cd", "monitoring", "nginx",
                "cloud", "networking", "python", "go", "git", "postgresql", "kafka", "http", "redis"]},
    {"code": "qa", "label": "QA / Тестирование", "short": "QA",
     "description": "Ручное и автоматизированное тестирование, качество продукта.",
     "skills": ["manual_testing", "test_design", "api_testing", "postman", "selenium", "playwright", "cypress",
                "pytest", "junit", "load_testing", "allure", "sql", "http", "rest", "python", "java", "javascript",
                "git", "ci_cd", "linux", "docker"]},
]
SPEC_CODES = [s["code"] for s in SPECIALIZATIONS]
SPEC_BY_CODE = {s["code"]: s for s in SPECIALIZATIONS}

# Ключевые слова специализаций для разбора свободного текста
SPEC_KEYWORDS: dict[str, list[str]] = {
    "backend": [r"backend", r"бэкенд\w*", r"бекенд\w*", r"back-end", r"серверн\w*"],
    "frontend": [r"frontend", r"фронтенд\w*", r"front-end", r"фронт\b", r"верстальщик\w*"],
    "data": [r"data scien\w*", r"\bml\b", r"machine learning", r"дата-сайент\w*", r"аналитик\w* данных", r"data analyst", r"data engineer\w*", r"ml-инженер\w*"],
    "devops": [r"devops", r"девопс\w*", r"\bsre\b", r"инфраструктур\w*", r"platform engineer\w*"],
    "qa": [r"\bqa\b", r"тестировщик\w*", r"тестировани\w*", r"автотест\w*", r"aqa"],
}

GRADE_KEYWORDS: dict[str, list[str]] = {
    "senior": [r"senior", r"сеньор\w*", r"синьор\w*", r"ведущ\w*", r"старш\w*", r"\blead\b", r"тимлид\w*"],
    "middle": [r"middle", r"мидл\w*"],
    "junior": [r"junior", r"джун\w*", r"младш\w*", r"начинающ\w*"],
    "intern": [r"стаж[её]р\w*", r"\bintern\b", r"стажировк\w*", r"студент\w*"],
}

WORK_FORMATS = [
    {"code": "office", "label": "Офис", "re": [r"офис\w*", r"\boffice\b"]},
    {"code": "hybrid", "label": "Гибрид", "re": [r"гибрид\w*", r"hybrid"]},
    {"code": "remote", "label": "Удалённо", "re": [r"удал[её]нн\w*", r"удал[её]нк\w*", r"remote", r"из любого города"]},
]
WORK_FORMAT_CODES = [w["code"] for w in WORK_FORMATS]

INDUSTRIES = [
    {"code": "fintech", "label": "Финтех и банки"},
    {"code": "ecommerce", "label": "E-commerce и ритейл"},
    {"code": "govtech", "label": "Госсектор"},
    {"code": "edtech", "label": "Образование"},
    {"code": "healthtech", "label": "Медицина"},
    {"code": "telecom", "label": "Телеком"},
    {"code": "industry", "label": "Промышленность"},
    {"code": "gamedev", "label": "Геймдев"},
    {"code": "media", "label": "Медиа и развлечения"},
    {"code": "logistics", "label": "Логистика и транспорт"},
    {"code": "security", "label": "Информационная безопасность"},
    {"code": "saas", "label": "ИТ-продукты и SaaS"},
]
INDUSTRY_CODES = [i["code"] for i in INDUSTRIES]

SOFT_SKILLS = [
    {"code": "communication", "label": "Коммуникабельность", "re": [r"коммуникабельн\w*", r"коммуникаци\w*", r"communication"]},
    {"code": "teamwork", "label": "Работа в команде", "re": [r"работ\w* в команде", r"командн\w*", r"teamwork", r"team player"]},
    {"code": "leadership", "label": "Лидерство", "re": [r"лидер\w*", r"leadership", r"руковод\w*"]},
    {"code": "mentoring", "label": "Наставничество", "re": [r"наставни\w*", r"менторств\w*", r"mentoring", r"\bментор\w*"]},
    {"code": "self_management", "label": "Самоорганизация", "re": [r"самоорганизац\w*", r"самостоятельн\w*", r"тайм-менеджмент\w*"]},
    {"code": "problem_solving", "label": "Решение проблем", "re": [r"решени\w* проблем", r"problem solving", r"аналитическ\w* мышлени\w*"]},
    {"code": "responsibility", "label": "Ответственность", "re": [r"ответственн\w*"]},
    {"code": "learning", "label": "Обучаемость", "re": [r"обучаем\w*", r"быстро обуча\w*", r"learning"]},
    {"code": "stress_resistance", "label": "Стрессоустойчивость", "re": [r"стрессоустойчив\w*"]},
    {"code": "presentation", "label": "Публичные выступления", "re": [r"публичн\w* выступлени\w*", r"доклад\w*", r"спикер\w*"]},
    {"code": "critical_thinking", "label": "Критическое мышление", "re": [r"критическ\w* мышлени\w*", r"critical thinking"]},
]
SOFT_SKILL_CODES = [s["code"] for s in SOFT_SKILLS]

ROLES = [
    {"code": "developer", "label": "Разработчик / инженер", "re": [r"разработчик\w*", r"developer", r"инженер\w*", r"engineer"]},
    {"code": "team_lead", "label": "Тимлид", "re": [r"тимлид\w*", r"team ?lead", r"руководител\w* (группы|команды)"]},
    {"code": "tech_lead", "label": "Техлид", "re": [r"техлид\w*", r"tech ?lead"]},
    {"code": "architect", "label": "Архитектор", "re": [r"архитектор\w*", r"architect"]},
    {"code": "mentor", "label": "Ментор", "re": [r"ментор\w*", r"наставник\w*", r"mentor"]},
    {"code": "analyst", "label": "Аналитик", "re": [r"аналитик\w*", r"analyst"]},
    {"code": "researcher", "label": "Исследователь", "re": [r"исследовател\w*", r"researcher", r"\bр&d\b"]},
    {"code": "captain", "label": "Капитан команды", "re": [r"капитан\w*", r"captain"]},
]
ROLE_CODES = [r["code"] for r in ROLES]

DECLINE_REASONS = [
    {"code": "salary", "label": "Не устраивает зарплата"},
    {"code": "stack", "label": "Не подходит стек или задачи"},
    {"code": "format", "label": "Не подходит формат работы или город"},
    {"code": "company", "label": "Не интересна компания или сфера"},
    {"code": "not_looking", "label": "Сейчас не ищу работу"},
    {"code": "other", "label": "Другое"},
]
DECLINE_REASON_CODES = [d["code"] for d in DECLINE_REASONS]

COMPLAINT_REASONS = [
    {"code": "fake", "label": "Похоже на фиктивную вакансию"},
    {"code": "spam", "label": "Массовая рассылка, не про мой профиль"},
    {"code": "conditions", "label": "Условия не соответствуют заявленным"},
    {"code": "rude", "label": "Некорректное общение"},
    {"code": "other", "label": "Другое"},
]
COMPLAINT_CODES = [c["code"] for c in COMPLAINT_REASONS]

JOB_STATUSES = [
    {"code": "active", "label": "Активно ищу работу"},
    {"code": "open", "label": "Открыт к предложениям"},
    {"code": "closed", "label": "Не ищу работу"},
]

# --- ФСП: веса для балла F (см. spec.md, «Механика подбора»)
FSP_LEVELS = {
    "international": {"label": "Международный", "gen": "международных", "weight": 1.0},
    "national": {"label": "Всероссийский", "gen": "всероссийских", "weight": 0.8},
    "interregional": {"label": "Межрегиональный", "gen": "межрегиональных", "weight": 0.6},
    "regional": {"label": "Региональный", "gen": "региональных", "weight": 0.5},
    "local": {"label": "Локальный", "gen": "локальных", "weight": 0.3},
}
FSP_RESULTS = {
    "winner": {"label": "Победитель", "weight": 1.0},
    "prize": {"label": "Призёр", "weight": 0.75},
    "finalist": {"label": "Финалист", "weight": 0.5},
    "participant": {"label": "Участник", "weight": 0.25},
}
FSP_DISCIPLINES = {
    "algorithmic": "Алгоритмическое программирование",
    "product": "Продуктовое программирование",
    "security": "Программирование систем информационной безопасности",
    "robotics": "Программирование робототехники",
    "uav": "Программирование беспилотных авиационных систем",
}

STATUS_LABELS = {
    "invitation": {"sent": "Отправлено", "viewed": "Просмотрено", "accepted": "Принято", "declined": "Отклонено",
                   "withdrawn": "Отозвано", "expired": "Истекло"},
    "application": {"sent": "Отправлен", "viewed": "Просмотрен", "invited": "Приглашение на интервью", "rejected": "Отказ"},
    "attempt": {"in_progress": "Идёт", "finished": "Завершён", "abandoned": "Прерван"},
    "result": {"confirmed": "Грейд подтверждён", "confirmed_plus": "Подтверждён с запасом", "not_confirmed": "Не подтверждён"},
    "assignment": {"assigned": "Ожидает ответа", "submitted": "Ответ отправлен", "skipped": "Пропущено"},
    "vacancy": {"published": "Опубликована", "closed": "Закрыта"},
}


def skill_label(code: str) -> str:
    s = SKILLS.get(code)
    return s["label"] if s else code


def skills_for_spec(spec: str) -> list[str]:
    return SPEC_BY_CODE[spec]["skills"] if spec in SPEC_BY_CODE else []


def category_label(spec: str | None, grade: str | None) -> str | None:
    if not spec or not grade or spec not in SPEC_BY_CODE or grade not in GRADE_BY_CODE:
        return None
    return f"{SPEC_BY_CODE[spec]['short']} · {GRADE_BY_CODE[grade]['label']}"


def public_dictionaries() -> dict:
    """Справочники для фронтенда (без регулярных выражений)."""
    return {
        "grades": GRADES,
        "specializations": SPECIALIZATIONS,
        "skills": {k: v["label"] for k, v in SKILLS.items()},
        "work_formats": [{"code": w["code"], "label": w["label"]} for w in WORK_FORMATS],
        "industries": INDUSTRIES,
        "soft_skills": [{"code": s["code"], "label": s["label"]} for s in SOFT_SKILLS],
        "roles": [{"code": r["code"], "label": r["label"]} for r in ROLES],
        "decline_reasons": DECLINE_REASONS,
        "complaint_reasons": COMPLAINT_REASONS,
        "job_statuses": JOB_STATUSES,
        "fsp_levels": {k: v["label"] for k, v in FSP_LEVELS.items()},
        "fsp_results": {k: v["label"] for k, v in FSP_RESULTS.items()},
        "fsp_disciplines": FSP_DISCIPLINES,
        "status_labels": STATUS_LABELS,
    }
