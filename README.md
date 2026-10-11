# ФСП Талант

Платформа подбора ИТ-специалистов с обратной механикой и верифицированным профилем. Кандидат проходит опрос и
адаптивный тест и получает категорию «специализация × грейд». Работодатель описывает потребность, получает
объяснённую подборку и сам приглашает кандидата. Зарплатная вилка в приглашении обязательна. Профиль обогащается
достижениями из реестра Федерации спортивного программирования (ФСП) по ФСП ID.

- Репозиторий: https://github.com/YaroslavGliznitsaYa/fsp-talent
- Требования и формулы: [spec.md](spec.md)
- Краткое описание подхода: [docs/approach.md](docs/approach.md)
- Сопроводительная документация: [docs/documentation.pdf](docs/documentation.pdf) (исходник — [docs/documentation.md](docs/documentation.md))
- Отчёт валидации с графиками: [docs/validation/report.md](docs/validation/report.md)
- Спецификация API: [docs/openapi.json](docs/openapi.json), в рантайме — `/docs`
- План работ: [plan.md](plan.md)

## Что умеет

| Кабинет кандидата | Кабинет работодателя |
|---|---|
| Профиль вручную или из PDF-резюме (автораспознавание), PDF-профиль | Профиль компании, подтверждение по ИНН и корпоративному домену |
| Опрос → выбор грейда → адаптивный тест (IRT, параметрические задания) → категория | Описание потребности текстом → автоматический разбор → объяснённая подборка |
| Повтор и смена грейда с ограничениями частоты, принятие грейда выше | Рекомендованные категории, фильтры без потери подборки, шорт-лист |
| Приглашения с обязательной вилкой, блок «Надёжность работодателя», жалоба | Банк кандидатов с фильтрами, анонимная карточка, контакты после принятия |
| Вакансии и самостоятельный отклик | Приглашения со статусами и квотой, вакансии и отклики |
| Регулярные задания от работодателей | Регулярные задания с рубрикой и оценкой 1–5 |
| Приватность, согласия (152-ФЗ), привязка ФСП ID (OIDC, Keycloak-совместимо) | Интеграция с ATS: вебхуки с HMAC-подписью, журнал доставок, экспорт кандидата в JSON |

Механики с живыми данными показаны на странице «Как это работает» (`/how-it-works`).

## Стек

| Слой | Технологии |
|---|---|
| Frontend | React 18.3, TypeScript 5.6, Vite 5.4, React Router 6.28, собственные CSS-токены |
| Backend | Python 3.12–3.13, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10, NumPy 2.1 (IRT), PyJWT, pypdf, fpdf2 |
| Хранение | SQLite (локально) или PostgreSQL 16 (Docker) |
| ФСП ID | mock-реестр с OIDC-эндпоинтами в формате Keycloak (`backend/fsp_mock`) |
| Почта | SMTP (Mailpit в Docker) или вывод в лог |

## Быстрый старт без Docker

Нужны Python 3.12+ и Node.js 20+.

```bash
# 1. Бэкенд
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m app.seed          # создаёт backend/data/app.db с демо-данными (~20 с)
.venv/bin/uvicorn app.main:app --port 8000

# 2. Фронтенд (в другом терминале)
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

На Windows вместо `.venv/bin/` используйте `.venv\Scripts\`.

- Swagger UI: http://localhost:8000/docs
- Mock ФСП ID встроен в бэкенд: http://localhost:8000/fsp/realms/fsp/.well-known/openid-configuration
- Письма (ссылка подтверждения email) пишутся в лог бэкенда. В демо-режиме ссылка также показывается на экране после регистрации.

## Запуск в Docker

```bash
cp .env.example .env     # при необходимости поменяйте значения
docker compose up --build
```

- Приложение: http://localhost:8080
- Swagger: http://localhost:8080/docs
- Почта (Mailpit): http://localhost:8025

Компоненты: `frontend` (nginx со сборкой SPA и проксированием `/api` и `/fsp`), `backend`, `fsp-mock`,
`db` (PostgreSQL 16), `mailpit`. Суммарный лимит памяти — около 1,1 ГБ. Демо-данные создаются при старте
(`SEED_ON_START=1`).

> Компоновка `docker-compose.yml` подготовлена, но на машине разработки Docker отсутствует, поэтому целиком она не прогонялась.
> Проверены её части: бэкенд и все автотесты на PostgreSQL 16, режим «mock ФСП отдельным сервисом за прокси».

## Демо-доступ

| Роль | Логин | Пароль | Что посмотреть |
|---|---|---|---|
| Кандидат | `candidate@demo.ru` | `demo12345` | Backend · Middle, привязан ФСП ID, есть входящие приглашения, задания, отклик |
| Работодатель | `employer@demo.ru` | `demo12345` | 2 потребности с готовыми подборками, шорт-лист, приглашения в разных статусах, подключённые вебхуки в демо-приёмник ATS |
| Неподтверждённая компания | `hr.smartcity@demo.ru` | `demo12345` | сниженная квота 5 приглашений в неделю |
| Остальные работодатели | `hr.logistics@demo.ru`, `hr.gamelab@demo.ru`, `hr.medtech@demo.ru`, `hr.cloud@demo.ru` | `demo12345` | |

Вход в mock ФСП ID: `FSP-100001` (4 достижения), `FSP-100002` (2), `FSP-100003` (нет истории), пароль `demo`.
Пример резюме для автораспознавания: [docs/samples/resume_sample.pdf](docs/samples/resume_sample.pdf).

## Сквозной сценарий для проверки

1. **Регистрация соискателя.** «Я ищу работу», согласие на обработку ПДн → ссылка подтверждения (на экране в демо-режиме).
2. **Профиль.** Загрузите `resume_sample.pdf` — поля и стек распознаются.
3. **Опрос и тест.** Пройдите опрос, выберите грейд и пройдите адаптивный тест (10–20 вопросов). Получите категорию.
4. **Публикация и ФСП.** В «Настройках» дайте согласие на публикацию и свяжите ФСП ID.
5. **Подборка.** Войдите как `employer@demo.ru` → «Подбор» → «Описать потребность». Вставьте текст и нажмите «Разобрать описание», сохраните. Получите подборку с баллом и причинами.
6. **Приглашение.** «Пригласить» с вилкой. Вернитесь кандидатом → «Приглашения»: виден блок «Надёжность работодателя» → «Принять». У работодателя открываются контакты, в «Компания → Интеграция с ATS» появляется доставленное событие `invitation.accepted`.
7. **Отклик.** «Вакансии» → «Откликнуться» → у работодателя отклик в разделе «Вакансии».

Механики с живыми данными — на странице «Как это работает» (`/how-it-works`).

## Структура

```
backend/
  app/
    api/            REST-роутеры: auth, candidate, tests, vacancies, employer, fsp, meta
    services/
      bank/         банк параметрических шаблонов (106 шт.) + самопроверка
      irt.py        модель 2PL, EAP-оценка θ, EM-калибровка
      testing.py    адаптивный тест, решение по грейду, ограничения частоты, детектор утечек
      matching.py   сила профиля, балл соответствия, причины, видимость
      nlp.py        разбор потребностей и резюме, TF-IDF
      pdf.py        разбор PDF-резюме и генерация PDF-профиля
      fsp_client.py OAuth/OIDC-клиент ФСП ID
    models.py, schemas.py, security.py, seed.py
  fsp_mock/         mock реестра ФСП и ФСП ID (Keycloak-совместимые пути)
  validation/       процедура валидации и графики → docs/validation/
  tests/            pytest
frontend/src/
  pages/candidate/  кабинет кандидата
  pages/employer/   кабинет работодателя
  components/       UI-компоненты, план теста, модалка приглашения
docs/               документация (md + pdf, build_pdf.py), OpenAPI, отчёт валидации, пример резюме
```

## Полезные команды

```bash
cd backend
.venv/bin/python -m pytest                          # 12 автотестов: правила ТЗ, доверие, вебхуки
TEST_DATABASE_URL=postgresql+psycopg://user@localhost/db .venv/bin/python -m pytest  # те же тесты на PostgreSQL
.venv/bin/python -m app.services.bank.selfcheck 3000  # самопроверка банка заданий на 3000 зёрнах
.venv/bin/python -m validation.run_validation       # валидация (~4 мин) → docs/validation/report.md + графики
.venv/bin/python -m app.seed --candidates 320       # пересоздать демо-данные (после обновления схемы — обязательно)

cd frontend
npm run build                                       # проверка типов и production-сборка

cd ..
pip install markdown && python docs/build_pdf.py    # PDF документации (нужен Google Chrome)
```

## Переменные окружения бэкенда

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite:///backend/data/app.db` | строка подключения SQLAlchemy |
| `SECRET_KEY` | dev-значение | подпись JWT — **обязательно сменить в продуктиве** |
| `FRONTEND_URL`, `BACKEND_PUBLIC_URL` | `http://localhost:5173`, `http://localhost:8000` | ссылки в письмах и redirect_uri OAuth |
| `FSP_BASE_URL`, `FSP_INTERNAL_URL` | `http://localhost:8000/fsp`, — | ФСП ID для браузера и для запросов сервер→сервер |
| `FSP_REALM`, `FSP_CLIENT_ID`, `FSP_CLIENT_SECRET` | `fsp`, `fsp-talent`, dev-значение | параметры клиента Keycloak |
| `FSP_MOCK_EMBEDDED` | `true` | встроить mock ФСП в процесс бэкенда |
| `FSP_HTTP_TRUST_ENV` | `false` | использовать системный прокси для запросов к ФСП |
| `SMTP_HOST`, `SMTP_PORT` | —, `1025` | SMTP; без хоста письма пишутся в лог |
| `DEMO_EXPOSE_LINKS` | `true` | показывать ссылку подтверждения на экране |
| `GRADE_COOLDOWN_DAYS`, `RETEST_SAME_GRADE_DAYS` | `90`, `30` | ограничения частоты смены грейда и повтора теста |
| `INVITE_QUOTA_WEEK`, `INVITE_QUOTA_UNVERIFIED` | `20`, `5` | квота приглашений подтверждённой и неподтверждённой компании |
| `COMPLAINTS_TO_SUSPEND` | `3` | жалоб, после которых приглашения компании приостанавливаются |
| `TASK_INTERVAL_DAYS` | `7` | периодичность регулярных заданий |
| `DEMO_WEBHOOK_URL` | `http://localhost:8000/api/system/webhook-echo` | куда демо-работодатель шлёт вебхуки |
