"""Пул шаблонов специализации «qa». Каждый шаблон регистрируется декоратором @template (см. base.py).

SQL-шаблоны вычисляют ответ, выполняя показанный кандидату запрос в sqlite3 (in-memory), поэтому ключ ответа
всегда совпадает с реальным результатом. pytest-шаблоны сверены прогоном pytest на зёрнах 0..49.
"""
import math
import itertools
import random
import sqlite3
from fractions import Fraction

from app.services.bank.base import template

_NAMES = ["anna", "oleg", "ira", "egor", "dina", "boris", "vera", "gleb"]


def _num(x) -> str:
    x = Fraction(x)
    if x.denominator == 1:
        return str(x.numerator)
    return f"{float(x):.4f}".rstrip("0").rstrip(".")


def _sql(query: str) -> list[tuple]:
    con = sqlite3.connect(":memory:")
    try:
        return con.execute(query).fetchall()
    finally:
        con.close()


# ---------------------------------------------------------------------------------------------- test design basics

@template(id="qa.test_types", pool="qa", topics=["manual_testing", "test_design"], fmt="concept", a=1.0, b=-1.5,
          title="Виды тестирования", variants=80)
def _test_types(rng: random.Random) -> dict:
    feature = rng.choice(["оформление заказа", "восстановление пароля", "загрузка аватара", "поиск по каталогу",
                          "экспорт отчёта"])
    bug = rng.randint(1000, 9999)
    names = {
        "retest": "Повторное (подтверждающее) тестирование",
        "regress": "Регрессионное тестирование",
        "smoke": "Смоук-тестирование",
        "load": "Нагрузочное тестирование",
        "explore": "Исследовательское тестирование",
        "uat": "Приёмочное тестирование",
        "black": "Тестирование методом чёрного ящика",
    }
    scen = {
        "retest": f"Разработчик исправил баг BUG-{bug} в сценарии «{feature}». Тестировщик проверяет именно этот "
                  f"сценарий, чтобы убедиться, что баг больше не воспроизводится.",
        "regress": f"После исправления BUG-{bug} в сценарии «{feature}» тестировщик прогоняет проверки соседних "
                   f"функций, чтобы убедиться, что ничего не сломалось.",
        "smoke": "Пришла новая сборка. Перед глубоким тестированием за 10 минут проверяют, что приложение "
                 "запускается и ключевые функции в принципе работают.",
        "load": f"Проверяют, сохраняет ли «{feature}» приемлемое время ответа при {rng.choice([200, 500, 1000])} "
                f"одновременных пользователях.",
        "explore": f"Тестировщик без готовых тест-кейсов изучает новый раздел «{feature}», одновременно "
                   f"придумывая и выполняя проверки.",
        "uat": "Представители заказчика проверяют систему на соответствие своим бизнес-процессам перед тем, как "
               "принять её.",
        "black": f"Тестировщик проверяет «{feature}» только по требованиям и интерфейсу, не заглядывая в код.",
    }
    key = rng.choice(list(scen))
    confusable = {"retest": ["regress", "smoke", "explore"], "regress": ["retest", "smoke", "uat"],
                  "smoke": ["regress", "retest", "load"], "load": ["smoke", "regress", "uat"],
                  "explore": ["black", "smoke", "uat"], "uat": ["smoke", "regress", "explore"],
                  "black": ["explore", "uat", "regress"]}[key]
    return {
        "stem": f"{scen[key]} Как называется такой вид тестирования?",
        "code": None,
        "correct": names[key],
        "distractors": [names[k] for k in confusable],
        "explanation": "Ретест — проверка исправленного дефекта; регресс — проверка, что изменения не сломали "
                       "остальное; смоук — быстрая проверка работоспособности сборки.",
    }


@template(id="qa.boundary_values", pool="qa", topics=["test_design"], fmt="calc", a=1.2, b=-1.3,
          title="Анализ граничных значений", variants=1000)
def _boundary_values(rng: random.Random) -> dict:
    field, lo_rng, span = rng.choice([("Возраст", (14, 21), (40, 70)), ("Количество товара", (1, 3), (10, 99)),
                                      ("Длина пароля (символов)", (6, 10), (6, 30)),
                                      ("Сумма перевода, ₽", (10, 100), (1000, 5000))])
    lo = rng.randint(*lo_rng)
    hi = lo + rng.randint(*span)
    three = rng.random() < 0.4

    def j(xs):
        return ", ".join(map(str, xs))

    two_pt = [lo - 1, lo, hi, hi + 1]
    three_pt = [lo - 1, lo, lo + 1, hi - 1, hi, hi + 1]
    inner = [lo, lo + 1, hi - 1, hi]
    if three:
        correct, cands = three_pt, [two_pt, inner, [lo - 1, lo + 1, hi - 1, hi + 1], [lo, (lo + hi) // 2, hi]]
    else:
        correct, cands = two_pt, [three_pt, inner, [lo, hi], [lo - 1, (lo + hi) // 2, hi + 1]]
    method = "трёхточечный: граница и оба соседа" if three else "двухточечный: граница и ближайшее значение за ней"
    return {
        "stem": f"Поле «{field}» принимает целые значения от {lo} до {hi} включительно. Какой набор тестовых "
                f"значений даёт анализ граничных значений ({method})?",
        "code": None,
        "correct": j(correct),
        "distractors": [j(c) for c in cands],
        "explanation": "Для каждой границы берутся сама граница и ближайшие значения по обе стороны "
                       "(в двухточечном варианте — только значение за границей).",
    }


@template(id="qa.severity_priority", pool="qa", topics=["manual_testing"], fmt="concept", a=1.0, b=-1.2,
          title="Серьёзность и приоритет дефекта", variants=60)
def _severity_priority(rng: random.Random) -> dict:
    opts = {"HH": "Серьёзность высокая, приоритет высокий", "HL": "Серьёзность высокая, приоритет низкий",
            "LH": "Серьёзность низкая, приоритет высокий", "LL": "Серьёзность низкая, приоритет низкий"}
    shop = rng.choice(["интернет-магазина", "банковского приложения", "сервиса доставки", "онлайн-кинотеатра"])
    scen = {
        "LH": [f"На главной странице {shop} в названии компании опечатка. Завтра запуск рекламной кампании.",
               f"В письме-подтверждении {shop} перепутан номер телефона поддержки (одна цифра)."],
        "HL": [f"Админка {shop} падает при экспорте отчёта в устаревший формат, которым пользуется пара "
               f"сотрудников; есть обходной путь через другой формат.",
               f"Приложение {shop} аварийно закрывается на снятой с поддержки версии ОС, доля таких "
               f"пользователей — {rng.choice(['0,1', '0,2', '0,05'])}%."],
        "HH": [f"Ни один пользователь {shop} не может оплатить заказ: кнопка оплаты возвращает ошибку 500.",
               f"После обновления {shop} пользователи не могут войти в аккаунт."],
        "LL": [f"В редко посещаемом разделе настроек {shop} иконка смещена на {rng.randint(2, 4)} пикселя.",
               f"В подсказке к необязательному полю профиля {shop} лишний пробел."],
    }
    key = rng.choice(list(scen))
    return {
        "stem": f"{rng.choice(scen[key])} Как оценить дефект?",
        "code": None,
        "correct": opts[key],
        "distractors": [v for k, v in opts.items() if k != key],
        "explanation": "Серьёзность — насколько дефект влияет на работу системы; приоритет — насколько срочно его "
                       "нужно исправить с точки зрения бизнеса. Это независимые оценки.",
    }


@template(id="qa.equivalence_classes", pool="qa", topics=["test_design"], fmt="calc", a=1.2, b=-0.6,
          title="Классы эквивалентности", variants=500)
def _equivalence_classes(rng: random.Random) -> dict:
    k = rng.choice([2, 3, 4])
    gaps = rng.choice([0, 0, 1])
    labels = rng.sample(["базовый", "бронзовый", "серебряный", "золотой", "платиновый", "премиум"], k)
    start = rng.choice([0, 1, 5, 10, 18])
    parts, cur = [], start
    gap_at = rng.randrange(1, k) if gaps else None
    for i in range(k):
        if i == gap_at:
            cur += rng.randint(5, 20)
        width = rng.randint(5, 40)
        parts.append(f"{cur}–{cur + width - 1} — {labels[i]}")
        cur += width
    correct = k + 2 + gaps
    unit = rng.choice(["баллов лояльности", "лет стажа", "покупок за год"])
    return {
        "stem": f"Тариф определяется по целому числу {unit}: " + "; ".join(parts) + ". Остальные значения "
                "система отклоняет с ошибкой. Сколько классов эквивалентности получится, если каждый "
                "непрерывный диапазон значений с одинаковым поведением считать отдельным классом?",
        "code": None,
        "correct": str(correct),
        "distractors": [str(x) for x in (k, k + 1, correct + 1, correct - 1 if gaps else k + 4, 2 * k + 2)
                        if x != correct],
        "explanation": f"Допустимых классов {k} (по одному на тариф), недопустимых {2 + gaps}: ниже минимума, "
                       f"выше максимума" + (" и разрыв между диапазонами." if gaps else "."),
    }


@template(id="qa.decision_table", pool="qa", topics=["test_design"], fmt="calc", a=1.2, b=-0.3,
          title="Таблица решений", variants=200)
def _decision_table(rng: random.Random) -> dict:
    bools = rng.sample(["пользователь авторизован", "есть промокод", "сумма заказа больше 5000 ₽",
                        "товар в наличии", "первый заказ", "подписка активна"], rng.choice([2, 3, 4]))
    multi = rng.choice([None, ("способ оплаты", ["карта", "СБП", "наличные"]),
                        ("доставка", ["курьер", "пункт выдачи", "самовывоз", "почта"])])
    total = 2 ** len(bools) * (len(multi[1]) if multi else 1)
    conds = [f"{b} (да/нет)" for b in bools]
    if multi:
        conds.append(f"{multi[0]} ({' / '.join(multi[1])})")
    n = len(bools)
    m = len(multi[1]) if multi else 0
    cands = [2 * n + m, 2 ** (n + (1 if multi else 0)), 2 ** n + m, n * max(m, 2), 2 ** (n + m) if m else 2 ** n * 3]
    return {
        "stem": "Скидка в корзине зависит от условий: " + "; ".join(conds) + ". Сколько правил (столбцов) "
                "будет в полной таблице решений, где перебраны все комбинации условий?",
        "code": None,
        "correct": str(total),
        "distractors": [str(c) for c in cands if c != total] + [str(total * 2), str(total // 2)],
        "explanation": "Полная таблица решений содержит произведение числа значений всех условий.",
    }


@template(id="qa.pairwise_count", pool="qa", topics=["test_design"], fmt="calc", a=1.2, b=1.0,
          title="Попарное тестирование (pairwise)", variants=300)
def _pairwise_count(rng: random.Random) -> dict:
    params = [("Тип пользователя", ["гость", "клиент", "партнёр", "администратор", "модератор"]),
              ("Способ оплаты", ["карта", "СБП", "счёт", "бонусы"]),
              ("Доставка", ["курьер", "самовывоз", "пункт выдачи"]),
              ("Язык интерфейса", ["ru", "en", "kk", "uz"]),
              ("Устройство", ["телефон", "планшет", "ПК"])]
    chosen = rng.sample(params, 3)
    sizes = [rng.randint(2, len(v)) for _, v in chosen]
    if len(set(sizes)) == 1 and rng.random() < 0.7:
        sizes[0] = max(2, sizes[0] - 1) if sizes[0] > 2 else 3
    desc = "; ".join(f"{name}: {', '.join(vals[:s])}" for (name, vals), s in zip(chosen, sizes))
    a, b, c = sorted(sizes, reverse=True)
    correct = a * b
    cands = [a * b * c, a + b + c, a * c, b * c, a, a * b + c, a * b - 1]
    return {
        "stem": f"Форма заказа имеет три независимых параметра. {desc}. Какое минимальное число тестов "
                f"покрывает все пары значений любых двух параметров?",
        "code": None,
        "correct": str(correct),
        "distractors": [str(x) for x in cands if x != correct],
        "explanation": f"Все пары значений двух самых больших параметров ({a}×{b}) должны встретиться в разных "
                       f"тестах, значит меньше {a * b} нельзя; третий параметр (≤ {b} значений) раскладывается "
                       f"по этим тестам так, что все его пары тоже покрыты.",
    }


# ---------------------------------------------------------------------------------------------- http / api

@template(id="qa.http_methods", pool="qa", topics=["http", "api_testing"], fmt="concept", a=1.2, b=-0.4,
          title="Идемпотентность и безопасность HTTP-методов", variants=100)
def _http_methods(rng: random.Random) -> dict:
    ent = rng.choice(["orders", "users", "carts", "tickets", "invoices"])
    rid = rng.randint(10, 999)
    variant = rng.randrange(5)
    if variant == 0:
        c = rng.choice(["PUT", "DELETE"])
        return {"stem": "Какой HTTP-метод по спецификации идемпотентен, но не является безопасным?",
                "code": None, "correct": c, "distractors": ["GET", "POST", "HEAD", "OPTIONS"],
                "explanation": "Безопасные методы (GET, HEAD, OPTIONS) не меняют состояние; PUT и DELETE меняют, "
                               "но повтор даёт тот же результат."}
    if variant == 1:
        return {"stem": "Какой из методов по спецификации HTTP не является идемпотентным?",
                "code": None, "correct": "POST", "distractors": ["PUT", "DELETE", "GET", "HEAD"],
                "explanation": "Повторный POST обычно создаёт ещё один ресурс."}
    if variant == 2:
        return {"stem": "Какой из методов является безопасным (не должен менять состояние сервера)?",
                "code": None, "correct": rng.choice(["GET", "HEAD"]), "distractors": ["POST", "PUT", "DELETE", "PATCH"],
                "explanation": "Безопасные методы — GET, HEAD, OPTIONS, TRACE."}
    if variant == 3:
        return {"stem": "Клиент не дождался ответа из-за таймаута и повторил запрос. Повтор какого запроса "
                        "безопасен без ключа идемпотентности?",
                "code": None, "correct": f"PUT /{ent}/{rid} с полным представлением ресурса",
                "distractors": [f"POST /{ent}", f"POST /{ent}/{rid}/pay", f"PATCH /{ent}/{rid} с операцией «+1 к количеству»"],
                "explanation": "PUT заменяет ресурс целиком — повтор приводит к тому же состоянию."}
    return {"stem": f"Тест дважды подряд отправляет DELETE /{ent}/{rid}; первый вызов вернул 204. Что корректно "
                    f"ожидать от второго вызова по семантике HTTP?",
            "code": None,
            "correct": "Состояние сервера не меняется; код ответа может быть другим (например, 404)",
            "distractors": ["Обязательно снова 204, иначе метод не идемпотентен",
                            "500: повторное удаление — ошибка сервера",
                            "Сервер удалит следующий по порядку ресурс"],
            "explanation": "Идемпотентность касается состояния сервера, а не одинаковости ответа."}


@template(id="qa.status_codes", pool="qa", topics=["api_testing", "http"], fmt="concept", a=1.1, b=-0.8,
          title="Коды ответа HTTP в тестировании API", variants=150)
def _status_codes(rng: random.Random) -> dict:
    ent, one = rng.choice([("orders", "заказ"), ("users", "пользователя"), ("tickets", "заявку"),
                           ("products", "товар")])
    rid = rng.randint(10, 9999)
    codes = {200: "200 OK", 201: "201 Created", 204: "204 No Content", 400: "400 Bad Request",
             401: "401 Unauthorized", 403: "403 Forbidden", 404: "404 Not Found", 405: "405 Method Not Allowed",
             409: "409 Conflict", 422: "422 Unprocessable Content", 429: "429 Too Many Requests",
             500: "500 Internal Server Error"}
    scen = [
        (f"POST /{ent} успешно создал {one}, в ответе — созданный объект и заголовок Location.", 201, [200, 204, 202]),
        (f"GET /{ent}/{rid} отправлен без заголовка Authorization к защищённому API.", 401, [403, 400, 404]),
        (f"Пользователь с валидным токеном обычного пользователя вызывает DELETE /admin/{ent}/{rid}, "
         f"доступный только администраторам.", 403, [401, 404, 405]),
        (f"DELETE /{ent}/{rid} успешно выполнен, тела ответа нет.", 204, [200, 201, 404]),
        ("POST /users с email, который уже зарегистрирован (поле уникально).", 409, [400, 422, 500]),
        (f"Клиент отправил {rng.choice([100, 300, 1000])} запросов за минуту при лимите "
         f"{rng.choice([60, 50, 30])} в минуту.", 429, [403, 503, 400]),
        (f"GET /{ent}/{rid} — такого объекта нет в базе.", 404, [204, 400, 410]),
        (f"В теле POST /{ent} передан синтаксически некорректный JSON (не хватает закрывающей скобки).", 400,
         [422, 500, 415]),
    ]
    codes[202], codes[410], codes[415], codes[503] = ("202 Accepted", "410 Gone", "415 Unsupported Media Type",
                                                      "503 Service Unavailable")
    text, c, d = rng.choice(scen)
    return {
        "stem": f"{text} Какой код ответа ожидаем по общепринятой семантике HTTP?",
        "code": None,
        "correct": codes[c],
        "distractors": [codes[x] for x in d],
        "explanation": "401 — не аутентифицирован, 403 — нет прав, 409 — конфликт с текущим состоянием, "
                       "201 — создан ресурс, 204 — успех без тела, 429 — превышен лимит.",
    }


# ---------------------------------------------------------------------------------------------- automation

@template(id="qa.locators", pool="qa", topics=["selenium", "playwright"], fmt="concept", a=1.1, b=-0.7,
          title="Устойчивые локаторы в UI-автотестах", variants=200)
def _locators(rng: random.Random) -> dict:
    text, tid = rng.choice([("Оформить заказ", "checkout-submit"), ("Войти", "login-button"),
                            ("Сохранить", "profile-save"), ("Добавить в корзину", "add-to-cart")])
    n = rng.randint(2, 6)
    variant = rng.randrange(3)
    if variant == 0:
        return {"stem": f"Какой CSS/XPath-локатор кнопки «{text}» наиболее устойчив к изменениям вёрстки?",
                "code": None,
                "correct": f'[data-testid="{tid}"]',
                "distractors": [f"/html/body/div[{n}]/div/form/button[1]",
                                f"div.form > div:nth-child({n}) > button",
                                f"#ember{rng.randint(100, 999)}",
                                f".css-{rng.choice(['1x2y3z', '9fk2ab', 'q81b0c'])}.btn"],
                "explanation": "Специальный тестовый атрибут не зависит от структуры DOM, стилей и "
                               "сгенерированных идентификаторов."}
    if variant == 1:
        return {"stem": f"Какой локатор Playwright для кнопки «{text}» рекомендуется и наиболее устойчив?",
                "code": None,
                "correct": f"page.getByRole('button', {{ name: '{text}' }})",
                "distractors": [f"page.locator('div:nth-child({n}) > button')",
                                f"page.locator('xpath=//*[@id=\"root\"]/div/div[{n}]/button')",
                                f"page.locator('.css-{rng.choice(['1x2y3z', '9fk2ab'])}')"],
                "explanation": "Локаторы по роли и доступному имени отражают то, как пользователь видит "
                               "страницу, и не зависят от вёрстки."}
    return {"stem": f"Автотест начал падать после того, как разработчик поменял местами два блока формы, хотя "
                    f"кнопка «{text}» осталась прежней. Какой локатор, скорее всего, использовался?",
            "code": None,
            "correct": f"/html/body/div[{n}]/form/div[3]/button",
            "distractors": [f'[data-testid="{tid}"]', f"getByRole('button', {{ name: '{text}' }})",
                            f"button[name=\"{tid}\"]"],
            "explanation": "Абсолютный XPath завязан на позиции элементов и ломается при любой перестановке."}


@template(id="qa.flaky_tests", pool="qa", topics=["selenium", "playwright", "test_design"], fmt="concept",
          a=1.2, b=0.5, title="Причины нестабильных (flaky) автотестов", variants=80)
def _flaky_tests(rng: random.Random) -> dict:
    page = rng.choice(["корзины", "профиля", "каталога", "оплаты"])
    pct = rng.choice([5, 10, 15, 20])
    variant = rng.randrange(5)
    if variant == 0:
        sec = rng.choice([1, 2, 3])
        return {"stem": f"UI-тест страницы {page} в CI падает примерно в {pct}% запусков с ошибкой «элемент не "
                        f"найден». Локально проходит.",
                "code": f"driver.find_element(By.ID, \"load-more\").click()\ntime.sleep({sec})\n"
                        f"driver.find_element(By.CSS_SELECTOR, \"[data-testid=item-21]\").click()",
                "code_lang": "python",
                "correct": "Фиксированный sleep: заменить на явное ожидание появления элемента",
                "distractors": [f"Мало ждём: увеличить sleep до {sec * 5} с",
                                "CI медленный: добавить автоматический перезапуск упавших тестов",
                                "Селектор по data-testid ненадёжен: заменить на XPath"],
                "explanation": "Время загрузки непостоянно; надёжнее ждать условие (WebDriverWait / авто-ожидание)."}
    if variant == 1:
        return {"stem": f"Тесты {page} по отдельности всегда проходят, а при прогоне всего набора в случайном "
                        f"порядке иногда падают. Самая вероятная причина?",
                "code": None,
                "correct": "Тесты зависят от общего состояния или данных, оставленных другими тестами",
                "distractors": ["Слишком много тестов в одном файле",
                                "Случайный порядок запуска запрещён в pytest",
                                "Браузер не успевает прогреться между тестами"],
                "explanation": "Каждый тест должен сам готовить и убирать свои данные."}
    if variant == 2:
        return {"stem": f"Тест проверяет, что заказ на странице {page} создан «сегодня», и падает только при "
                        f"ночных запусках CI около полуночи. Причина?",
                "code": "assert order.created_at.date() == date.today()",
                "code_lang": "python",
                "correct": "Зависимость от текущего времени и часового пояса: время нужно зафиксировать",
                "distractors": ["Ночью в CI меньше ресурсов, база отвечает медленнее",
                                "date.today() работает только в локальном окружении",
                                "Ночью в базе другие индексы"],
                "explanation": "Создание и проверка могут попасть в разные сутки (или разные часовые пояса)."}
    if variant == 3:
        w = rng.choice([4, 8, 16])
        return {"stem": f"После включения параллельного запуска (потоков: {w}) тесты {page} стали случайно "
                        f"падать: в корзине оказываются «чужие» товары. Причина?",
                "code": None,
                "correct": "Параллельные тесты используют один и тот же тестовый аккаунт",
                "distractors": ["Слишком много потоков для браузера, нужно не больше двух",
                                "Параллельный запуск ломает локаторы",
                                "Нужно добавить sleep между тестами"],
                "explanation": "Каждому потоку нужны изолированные данные (свой пользователь, своя корзина)."}
    return {"stem": f"Тест сохраняет ссылку на строку таблицы {page}, затем меняет фильтр и кликает по ней — "
                    f"иногда получает StaleElementReferenceException. Причина?",
            "code": "row = driver.find_element(By.CSS_SELECTOR, \"tr.item\")\napply_filter(\"active\")\nrow.click()",
            "code_lang": "python",
            "correct": "Таблица перерисовалась, сохранённый элемент устарел — искать его заново",
            "distractors": ["Строка скрыта CSS — нужен JavaScript-клик",
                            "Неверный селектор tr.item — нужен XPath",
                            "Нужно увеличить implicit wait"],
            "explanation": "После перерисовки DOM старая ссылка на элемент недействительна."}


@template(id="qa.py_status_stats", pool="qa", topics=["python", "api_testing"], fmt="output", a=1.1, b=-0.5,
          title="Python для QA: подсчёт по словарю", variants=2000, verify=True)
def _py_status_stats(rng: random.Random) -> dict:
    while True:
        codes = [rng.choice([200, 200, 201, 204, 301, 400, 404, 404, 500, 502]) for _ in range(rng.randint(6, 8))]
        groups = [f"{c // 100}xx" for c in codes]
        order = list(dict.fromkeys(groups))
        if len(order) >= 3 and order != sorted(order):
            break
    stats = {g: groups.count(g) for g in order}
    by_code = {}
    for c in codes:
        by_code[str(c)] = by_code.get(str(c), 0) + 1
    var = rng.choice(["responses", "codes", "statuses"])
    code = (f"{var} = {codes}\nstats = {{}}\nfor code in {var}:\n    group = f\"{{code // 100}}xx\"\n"
            f"    stats[group] = stats.get(group, 0) + 1\nprint(stats)")
    alt_sorted = {g: stats[g] for g in sorted(stats)}
    alt_one = {g: 1 for g in order}
    alt_last = dict(stats)
    alt_last[order[0]] = stats[order[0]] - 1 if stats[order[0]] > 1 else stats[order[0]] + 1
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": str(stats),
        "distractors": [str(alt_sorted), str(alt_one), str(alt_last), str({int(k): v for k, v in by_code.items()})],
        "explanation": "dict.get(key, 0) возвращает 0 для нового ключа; словарь сохраняет порядок первой вставки.",
    }


@template(id="qa.pytest_collect", pool="qa", topics=["pytest", "python"], fmt="calc", a=1.3, b=0.6,
          title="pytest: parametrize и параметризованные фикстуры", variants=2000)
def _pytest_collect(rng: random.Random) -> dict:
    while True:
        p1 = rng.randint(2, 4)
        p2 = rng.choice([0, 2, 3])
        fx = rng.choice([0, 2, 3])
        plain = rng.randint(1, 2)
        tup = rng.choice([0, 2, 3])
        if p2 or fx or tup:
            break
    main = p1 * (p2 or 1) * (fx or 1)
    extra = tup * (fx or 1) if tup and rng.random() < 0.5 else tup
    uses_fx_in_tup = tup and extra != tup
    total = main + extra + plain
    vals1 = rng.sample([1, 5, 10, 50, 100, 0, -1], p1)
    lines = ["import pytest", ""]
    if fx:
        langs = rng.sample(["ru", "en", "kk", "de"], fx)
        lines += [f"@pytest.fixture(params={langs})", "def lang(request):", "    return request.param", ""]
    lines.append(f"@pytest.mark.parametrize(\"qty\", {vals1})")
    args = ["qty"]
    if p2:
        lines.append(f"@pytest.mark.parametrize(\"role\", {rng.sample(['guest', 'user', 'admin', 'owner'], p2)})")
        args.append("role")
    if fx:
        args.append("lang")
    lines += [f"def test_cart({', '.join(args)}): ...", ""]
    if tup:
        pairs = [(rng.randint(1, 9), rng.randint(1, 9)) for _ in range(tup)]
        lines.append(f"@pytest.mark.parametrize(\"a, b\", {pairs})")
        lines += [f"def test_sum(a, b{', lang' if uses_fx_in_tup else ''}): ...", ""]
    for i in range(plain):
        lines.append(f"def test_{['ping', 'health', 'version'][i]}(): ...")
    cands = [p1 + p2 + fx + tup + plain, main + tup + plain if extra != tup else main + tup * 2 + plain,
             p1 * (p2 or 1) + extra + plain, main + extra, total + 1, total - 1,
             p1 * (p2 or 1) * (fx or 1) * (tup or 1) + plain, total + 2, total * 2, total - 2]
    return {
        "stem": "Сколько тестов соберёт pytest из этого файла (pytest --collect-only)?",
        "code": "\n".join(lines),
        "code_lang": "python",
        "correct": str(total),
        "distractors": [str(c) for c in cands if c != total],
        "explanation": "Несколько декораторов parametrize перемножаются; параметризованная фикстура умножает "
                       "число тестов, которые её используют; кортежи в parametrize — по одному тесту на кортеж.",
    }


@template(id="qa.pytest_fixture_scope", pool="qa", topics=["pytest", "python"], fmt="calc", a=1.3, b=1.3,
          title="pytest: область видимости фикстур", variants=1000)
def _pytest_fixture_scope(rng: random.Random) -> dict:
    scope = rng.choice(["function", "class", "module"])
    k = rng.randint(2, 4)  # параметры функции test_search
    m1 = rng.randint(1, 3)
    m2 = rng.choice([0, 1, 2])
    use_fn = scope != "class"
    if scope == "function":
        correct = (k if use_fn else 0) + m1 + m2
    elif scope == "class":
        correct = 1 + (1 if m2 else 0)
    else:
        correct = 1
    tests_total = (k if use_fn else 0) + m1 + m2 + 1
    blocks = [["import pytest"], [f"@pytest.fixture(scope=\"{scope}\")", "def db():", "    print(\"connect\")"]]
    if use_fn:
        blocks.append([f"@pytest.mark.parametrize(\"q\", {rng.sample(['a', 'b', 'c', 'd', 'e'], k)})",
                       "def test_search(db, q): ..."])
    blocks.append(["class TestUsers:"] + [f"    def test_{n}(self, db): ..." for n in ["create", "update", "delete"][:m1]])
    if m2:
        blocks.append(["class TestOrders:"] + [f"    def test_{n}(self, db): ..." for n in ["list", "cancel"][:m2]])
    blocks.append(["def test_ping(): ..."])
    lines = []
    sep = sum(len(b) for b in blocks) + len(blocks) - 1 <= 15
    for b in blocks:
        if lines and (sep or b is blocks[1]):
            lines.append("")
        lines += b
    cands = [tests_total, tests_total - 1, (k if use_fn else 0) + m1 + m2, 1, 1 + (1 if m2 else 0), m1 + m2,
             (1 if use_fn else 0) + m1 + m2, 2 + (1 if m2 else 0), correct + 1, correct + 2, correct + 3]
    return {
        "stem": "Сколько раз будет выведено «connect» при запуске всех тестов этого файла (pytest -s)?",
        "code": "\n".join(lines),
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(c) for c in cands if c != correct],
        "explanation": "function — фикстура создаётся для каждого теста (и каждого набора параметров), class — "
                       "один раз на класс, module — один раз на файл; тесты, не запрашивающие фикстуру, её не "
                       "создают.",
    }


# ---------------------------------------------------------------------------------------------- sql

def _values(rows: list[tuple], per_line: int = 2) -> str:
    def lit(v):
        return "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else str(v))

    items = ["(" + ", ".join(lit(v) for v in r) + ")" for r in rows]
    return ",\n".join("  " + ", ".join(items[i:i + per_line]) for i in range(0, len(items), per_line))


@template(id="qa.sql_group_having", pool="qa", topics=["sql"], fmt="output", a=1.3, b=0.1,
          title="SQL: GROUP BY, WHERE и HAVING", variants=3000)
def _sql_group_having(rng: random.Random) -> dict:
    while True:
        names = rng.sample(_NAMES, 4)
        rows = [(rng.choice(names), rng.choice(["paid", "paid", "new", "cancelled"]), rng.randrange(50, 901, 10))
                for _ in range(8)]
        kind = rng.choice(["count", "sum"])
        if kind == "count":
            having, alt_having = "COUNT(*) >= 2", "COUNT(*) > 2"
        else:
            x = rng.randrange(300, 1201, 100)
            having, alt_having = f"SUM(amount) > {x}", f"SUM(amount) < {x}"
        cte = f"WITH orders(customer, status, amount) AS (VALUES\n{_values(rows)})\n"

        def q(where=True, hv=having):
            return (cte + "SELECT customer\nFROM orders\n" + ("WHERE status = 'paid'\n" if where else "")
                    + f"GROUP BY customer\nHAVING {hv};")

        def res(sql):
            return ", ".join(sorted(r[0] for r in _sql(sql))) or "(пусто)"

        correct = res(q())
        cands = [res(q(where=False)), res(q(hv=alt_having)), res(q(where=False, hv=alt_having)),
                 ", ".join(sorted({r[0] for r in rows if r[1] == "paid"})) or "(пусто)"]
        if correct != "(пусто)" and len(set(cands) - {correct}) >= 2:
            break
    pool = sorted({r[0] for r in rows})
    # Запасные дистракторы: все непустые подмножества клиентов в случайном порядке — хватает при любых данных
    subsets = [", ".join(sorted(c)) for k in range(1, len(pool) + 1) for c in itertools.combinations(pool, k)]
    rng.shuffle(subsets)
    cands.extend(subsets + ["(пусто)"])
    return {
        "stem": "Какие клиенты попадут в результат запроса? (Перечислены в алфавитном порядке.)",
        "code": q(),
        "code_lang": "sql",
        "correct": correct,
        "distractors": cands,
        "explanation": "WHERE фильтрует строки до группировки, HAVING — группы после агрегации.",
    }


@template(id="qa.sql_left_join_count", pool="qa", topics=["sql"], fmt="calc", a=1.3, b=0.8,
          title="SQL: LEFT JOIN и COUNT", variants=3000)
def _sql_left_join_count(rng: random.Random) -> dict:
    while True:
        users = list(enumerate(rng.sample(_NAMES, rng.randint(4, 5)), start=1))
        n_orders = rng.randint(4, 6)
        orders = [(100 + i, rng.choice([u[0] for u in users] + [9])) for i in range(n_orders)]
        cte = (f"WITH users(id, name) AS (VALUES\n{_values(users, 3)}),\norders(id, user_id) AS (VALUES\n"
               f"{_values(orders, 3)})\n")
        forms = {
            "lj_star": "SELECT COUNT(*)\nFROM users u LEFT JOIN orders o ON o.user_id = u.id;",
            "lj_col": "SELECT COUNT(o.id)\nFROM users u LEFT JOIN orders o ON o.user_id = u.id;",
            "lj_null": "SELECT COUNT(*)\nFROM users u LEFT JOIN orders o ON o.user_id = u.id\nWHERE o.id IS NULL;",
            "ij_star": "SELECT COUNT(*)\nFROM users u JOIN orders o ON o.user_id = u.id;",
        }
        vals = {k: _sql(cte + v)[0][0] for k, v in forms.items()}
        key = rng.choice(["lj_star", "lj_star", "lj_col", "lj_null"])
        correct = vals[key]
        cands = [v for k, v in vals.items() if k != key] + [len(orders), len(users), len(orders) + len(users)]
        if len(set(cands) - {correct}) >= 3 and vals["lj_null"] >= 1:
            break
    return {
        "stem": "Какое число вернёт запрос?",
        "code": cte + forms[key],
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "LEFT JOIN сохраняет пользователей без заказов (с NULL в полях заказа) и размножает "
                       "пользователей с несколькими заказами; COUNT(*) считает строки, COUNT(o.id) — только "
                       "непустые значения; заказы с несуществующим user_id в LEFT JOIN от users не попадают.",
    }


@template(id="qa.sql_not_in_null", pool="qa", topics=["sql"], fmt="calc", a=1.5, b=2.0,
          title="SQL: NOT IN, NOT EXISTS и NULL", variants=2000)
def _sql_not_in_null(rng: random.Random) -> dict:
    while True:
        cust = list(enumerate(rng.sample(_NAMES, rng.randint(5, 6)), start=1))
        buyers = rng.sample([c[0] for c in cust], rng.randint(2, 3))
        orders = [(200 + i, rng.choice(buyers)) for i in range(rng.randint(3, 4))]
        orders.insert(rng.randint(1, len(orders)), (200 + len(orders), None))
        orders = [(200 + i, u) for i, (_, u) in enumerate(orders)]
        if orders[0][1] is None:
            continue
        cte = (f"WITH customers(id, name) AS (VALUES\n{_values(cust, 3)}),\norders(id, customer_id) AS (VALUES\n"
               f"{_values(orders, 3)})\n")
        forms = {
            "not_in": "SELECT COUNT(*) FROM customers\nWHERE id NOT IN (SELECT customer_id FROM orders);",
            "not_exists": "SELECT COUNT(*) FROM customers c\nWHERE NOT EXISTS (\n  SELECT 1 FROM orders o "
                          "WHERE o.customer_id = c.id);",
            "in": "SELECT COUNT(*) FROM customers\nWHERE id IN (SELECT customer_id FROM orders);",
        }
        vals = {k: _sql(cte + v)[0][0] for k, v in forms.items()}
        key = rng.choice(["not_in", "not_in", "not_in", "not_exists"])
        correct = vals[key]
        no_orders = len(cust) - len(set(buyers) & {o[1] for o in orders})
        cands = [no_orders, 0, len(cust), vals["in"], no_orders - 1, no_orders + 1, len(cust) - 1]
        if vals["not_exists"] == no_orders and vals["not_in"] == 0 and len(set(cands) - {correct}) >= 3:
            break
    code = cte + forms[key]
    return {
        "stem": "Что вернёт запрос (стандартная семантика SQL; так ведут себя PostgreSQL и SQLite)?",
        "code": code,
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "Если подзапрос в NOT IN возвращает NULL, условие id NOT IN (…) для любого id равно NULL "
                       "или FALSE, и строк не будет. NOT EXISTS сравнивает построчно и NULL не мешает.",
    }


# ---------------------------------------------------------------------------------------------- load testing

@template(id="qa.percentile", pool="qa", topics=["load_testing"], fmt="calc", a=1.3, b=0.3,
          title="Перцентили времени ответа", variants=3000)
def _percentile(rng: random.Random) -> dict:
    while True:
        vals = rng.sample(range(80, 900, 5), 10)
        p = rng.choice([50, 70, 80, 90])
        rank = math.ceil(p / 100 * len(vals))
        s = sorted(vals)
        correct = s[rank - 1]
        mean = round(sum(vals) / len(vals))
        cands = [s[rank], s[rank - 2], mean, vals[rank - 1], max(vals)]
        if len(set(cands) - {correct}) >= 3:
            break
    return {
        "stem": f"Время ответа 10 запросов (мс) приведено ниже. Чему равен p{p} по методу ближайшего ранга "
                f"(значение с номером ⌈{p / 100:g} · N⌉ в списке, отсортированном по возрастанию)?",
        "code": ", ".join(map(str, vals)),
        "code_lang": "text",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": f"Сортируем: {s}; ⌈{p / 100:g}·10⌉ = {rank}, {rank}-е значение — {correct}.",
    }


@template(id="qa.littles_law", pool="qa", topics=["load_testing"], fmt="calc", a=1.3, b=1.2,
          title="Закон Литтла в нагрузочном тестировании", variants=1500)
def _littles_law(rng: random.Random) -> dict:
    while True:
        r = Fraction(rng.choice(["0.5", "1", "1.5", "2", "3", "0.2", "0.8"]))
        z = Fraction(rng.choice([2, 3, 4, 5, 8, 10]))
        x = rng.randint(4, 60)
        n = x * (r + z)
        if n.denominator == 1 and 10 <= n <= 1000:
            break
    ask = rng.choice(["x", "n", "r"])
    if ask == "x":
        stem = (f"Закрытая модель нагрузки, число виртуальных пользователей — {n}. Каждый отправляет запрос, "
                f"ждёт ответ (в среднем {_num(r)} с) и делает паузу {_num(z)} с перед следующим. Какую пропускную "
                f"способность (запросов в секунду) покажет тест в установившемся режиме?")
        correct, cands = x, [n / r, n / z, n * (r + z), n / (r + z + 1), Fraction(n) / 10]
    elif ask == "n":
        stem = (f"Нужно подать нагрузку {x} RPS (запросов в секунду). Среднее время ответа — {_num(r)} с, пауза "
                f"между запросами одного пользователя (think time) — {_num(z)} с. Сколько виртуальных "
                f"пользователей потребуется?")
        correct, cands = n, [x * r, x * z, Fraction(x) / (r + z), x * (r + z) * 2, x]
    else:
        stem = (f"Тест: число виртуальных пользователей — {n}, think time {_num(z)} с, измеренная пропускная "
                f"способность {x} RPS (запросов в секунду). Каково среднее время ответа (с)?")
        correct, cands = r, [Fraction(n, x), Fraction(n, x) + z, z - r if z > r else z + r, Fraction(x, n) * z]
    return {
        "stem": stem,
        "code": None,
        "correct": _num(correct),
        "distractors": [_num(c) for c in cands + [correct * 2, correct + z, correct * 3]
                        if c != correct and c > 0 and (Fraction(c) * 100).denominator == 1],
        "explanation": "Закон Литтла для закрытой модели: N = X · (R + Z), где N — пользователи, X — пропускная "
                       "способность, R — время ответа, Z — think time.",
    }
