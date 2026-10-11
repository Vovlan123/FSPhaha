"""Пул шаблонов специализации «backend». Каждый шаблон регистрируется декоратором @template (см. base.py)."""
import math
import random

from app.services.bank.base import template

_NAMES = ["anna", "boris", "vera", "gleb", "dina", "egor", "ilya", "kira", "lev", "maya"]


def _sec(x: int) -> str:
    return f"≈ {x} с"


# --- REST: методы и пути ---------------------------------------------------------------------------
_REST = [
    ("users", "orders", "пользователя", "заказы", "заказ", "заказа"),
    ("projects", "tasks", "проекта", "задачи", "задачу", "задачи"),
    ("courses", "lessons", "курса", "уроки", "урок", "урока"),
    ("shops", "products", "магазина", "товары", "товар", "товара"),
    ("authors", "books", "автора", "книги", "книгу", "книги"),
]


@template(id="backend.rest_crud", pool="backend", topics=["rest", "http"], fmt="concept", a=1.0, b=-1.5,
          title="Проектирование REST API", variants=500)
def _rest_crud(rng: random.Random) -> dict:
    par, ch, par_gen, ch_pl, ch_acc, ch_gen = rng.choice(_REST)
    pid, cid = rng.randint(2, 99), rng.randint(100, 999)
    cases = [
        (f"получить все {ch_pl} {par_gen} {pid}", f"GET /{par}/{pid}/{ch}",
         [f"POST /{par}/{pid}/{ch}", f"GET /get_{ch}?{par}={pid}", f"PUT /{par}/{pid}/{ch}"]),
        (f"создать {ch_acc} для {par_gen} {pid}", f"POST /{par}/{pid}/{ch}",
         [f"GET /{par}/{pid}/{ch}/create", f"PUT /{par}/{pid}", f"DELETE /{par}/{pid}/{ch}"]),
        (f"изменить только поле status у {ch_gen} {cid}", f"PATCH /{ch}/{cid}",
         [f"POST /{ch}/{cid}/update", f"GET /{ch}/{cid}?status=done", f"DELETE /{ch}/{cid}"]),
        (f"полностью заменить {ch_acc} {cid} новым представлением", f"PUT /{ch}/{cid}",
         [f"POST /{ch}/{cid}/replace", f"GET /{ch}/{cid}", f"DELETE /{ch}/{cid}"]),
        (f"удалить {ch_acc} {cid}", f"DELETE /{ch}/{cid}",
         [f"POST /{ch}/{cid}/delete", f"GET /{ch}/delete/{cid}", f"PUT /{ch}/{cid}"]),
        (f"получить {ch_acc} {cid}", f"GET /{ch}/{cid}",
         [f"POST /{ch}/{cid}", f"GET /get_{ch[:-1]}/{cid}", f"PUT /{ch}/{cid}"]),
    ]
    action, correct, distractors = rng.choice(cases)
    return {
        "stem": f"Как по соглашениям REST оформить запрос, чтобы {action}?",
        "correct": correct,
        "distractors": distractors,
        "explanation": "Ресурсы — существительные во множественном числе, действие задаёт метод: GET читает, POST создаёт "
                       "в коллекции, PUT заменяет целиком, PATCH меняет частично, DELETE удаляет.",
    }


# --- SQL: фильтрация -------------------------------------------------------------------------------
@template(id="backend.sql_filter_count", pool="backend", topics=["sql"], fmt="calc", a=1.1, b=-1.3,
          title="Фильтрация в SQL (WHERE)", variants=2000)
def _sql_filter_count(rng: random.Random) -> dict:
    cats = rng.sample(["books", "games", "music", "tools", "toys", "food"], 3)
    x, y = cats[0], cats[1]
    for _ in range(300):
        rows = [(i, rng.choice(cats), rng.choice(range(100, 901, 50))) for i in range(1, 8)]
        prices = [r[2] for r in rows]
        kind = rng.randrange(3)
        if kind == 0:
            in_x = [r[2] for r in rows if r[1] == x]
            if not in_x:
                continue
            p = rng.choice(in_x)  # есть строка ровно с ценой p: проверяется строгость >
            where = f"category = '{x}' AND price > {p}"
            correct = sum(r[1] == x and r[2] > p for r in rows)
            cands = [sum(r[1] == x and r[2] >= p for r in rows), sum(r[1] == x or r[2] > p for r in rows),
                     sum(r[1] == x for r in rows), sum(r[2] > p for r in rows)]
        elif kind == 1:
            if len(set(prices)) < 3:
                continue
            lo, hi = sorted(rng.sample(sorted(set(prices)), 2))
            where = f"price BETWEEN {lo} AND {hi}"
            correct = sum(lo <= v <= hi for v in prices)
            cands = [sum(lo < v < hi for v in prices), sum(lo <= v < hi for v in prices),
                     sum(lo < v <= hi for v in prices), correct + 1]
        else:
            p = rng.choice(prices)
            where = f"category IN ('{x}', '{y}') AND price < {p}"
            correct = sum(r[1] in (x, y) and r[2] < p for r in rows)
            cands = [sum(r[1] in (x, y) and r[2] <= p for r in rows), sum(r[1] in (x, y) for r in rows),
                     sum(r[2] < p for r in rows), sum(r[1] in (x, y) or r[2] < p for r in rows)]
        if len(set(cands) - {correct}) >= 3:
            break
    table = "\n".join(f"-- {i:>2} | {c:<5} | {pr}" for i, c, pr in rows)
    return {
        "stem": "Какое число вернёт запрос?",
        "code": f"-- products\n-- id | category | price\n{table}\nSELECT COUNT(*)\nFROM products\nWHERE {where};",
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands if c != correct],
        "explanation": "BETWEEN включает обе границы, > и < — строгие сравнения, AND требует выполнения обоих условий.",
    }


# --- SQL: GROUP BY / HAVING -------------------------------------------------------------------------
@template(id="backend.sql_group_having", pool="backend", topics=["sql"], fmt="calc", a=1.2, b=-0.6,
          title="Группировка: WHERE и HAVING", variants=2000)
def _sql_group_having(rng: random.Random) -> dict:
    custs = rng.sample(_NAMES[:6], 4)

    def groups(rs: list) -> dict:
        g: dict = {}
        for _, c, a in rs:
            g.setdefault(c, []).append(a)
        return g

    def fmt(names: list) -> str:
        return ", ".join(sorted(names)) if names else "(пусто)"

    for _ in range(500):
        rows = [(i, rng.choice(custs), rng.choice(range(50, 501, 10))) for i in range(1, 9)]
        w = rng.choice(range(100, 401, 50))
        filtered = [r for r in rows if r[2] >= w]
        if rng.random() < 0.4:
            s = rng.choice(range(300, 801, 100))
            having, ok, alt = f"SUM(amount) > {s}", (lambda a, s=s: sum(a) > s), (lambda a, s=s: sum(a) >= s - 100)
            sel = "SUM(amount) AS total"
        else:
            having, ok, alt = "COUNT(*) >= 2", (lambda a: len(a) >= 2), (lambda a: len(a) > 2)
            sel = "COUNT(*) AS cnt"
        res = sorted(c for c, a in groups(filtered).items() if ok(a))
        no_where = sorted(c for c, a in groups(rows).items() if ok(a))
        alt_res = sorted(c for c, a in groups(filtered).items() if alt(a))
        all_groups = sorted(groups(filtered))
        ask_names = rng.random() < 0.5
        if ask_names:
            correct = fmt(res)
            cands = [fmt(no_where), fmt(alt_res), fmt(all_groups), fmt(sorted(set(custs) - set(res)))]
        else:
            correct = str(len(res))
            cands = [str(len(no_where)), str(len(alt_res)), str(len(all_groups)), str(len(filtered))]
        if res and len(set(cands) - {correct}) >= 3:
            break
    table = "\n".join(f"-- {i:>2} | {c:<5} | {a}" for i, c, a in rows)
    select = "SELECT customer" if ask_names else f"SELECT customer, {sel}"
    code = (f"-- orders\n-- id | customer | amount\n{table}\n{select}\nFROM orders\nWHERE amount >= {w}\n"
            f"GROUP BY customer\nHAVING {having};")
    return {
        "stem": "Какие покупатели попадут в результат?" if ask_names else "Сколько строк вернёт запрос?",
        "code": code,
        "code_lang": "sql",
        "correct": correct,
        "distractors": cands,
        "explanation": "Сначала WHERE отбрасывает строки, затем идёт группировка, и только потом HAVING фильтрует группы "
                       "по агрегатам, посчитанным по оставшимся строкам.",
    }


# --- HTTP: идемпотентность и безопасность методов ---------------------------------------------------
@template(id="backend.http_idempotency", pool="backend", topics=["http", "rest"], fmt="concept", a=1.1, b=-0.5,
          title="Идемпотентность методов HTTP", variants=200)
def _http_idempotency(rng: random.Random) -> dict:
    res = rng.choice(["orders", "users", "carts", "articles", "devices"])
    rid = rng.randint(2, 999)
    field = rng.choice(["views", "likes", "balance", "attempts"])
    kind = rng.randrange(6)
    if kind == 0:
        stem = "Какой из методов НЕ является идемпотентным по спецификации HTTP?"
        correct, d = "POST", rng.sample(["PUT", "DELETE", "GET", "HEAD", "OPTIONS"], 3)
    elif kind == 1:
        m = rng.choice(["PUT", "DELETE"])
        body = " с полным представлением объекта" if m == "PUT" else ""
        stem = (f"Клиент отправил {m} /{res}/{rid}{body} и не дождался ответа из-за таймаута. "
                f"Можно ли безопасно повторить запрос без дополнительных механизмов?")
        correct = f"Да: {m} идемпотентен, повтор приведёт к тому же состоянию"
        d = ["Нет: любой повтор после таймаута может создать дубликат",
             "Нет: идемпотентны только безопасные методы (GET, HEAD)", "Да, но только если тело запроса пустое"]
    elif kind == 2:
        stem = (f"Клиент отправил POST /{res}/{rid}/payments и не дождался ответа из-за таймаута. "
                f"Можно ли безопасно повторить запрос без дополнительных механизмов?")
        correct = "Нет: POST не идемпотентен, повтор может создать второй платёж"
        d = ["Да: все методы HTTP идемпотентны", "Да: сервер сам отбросит дубликат по URL",
             "Да, если повторить в течение минуты"]
    elif kind == 3:
        stem = "Какой набор методов безопасен (safe), то есть не должен изменять состояние сервера?"
        correct, d = "GET, HEAD, OPTIONS", ["GET, PUT, DELETE", "GET, POST, HEAD", "PUT, PATCH, DELETE"]
    elif kind == 4:
        stem = f"Первый DELETE /{res}/{rid} вернул 204, повторный — 404. Нарушает ли это идемпотентность?"
        correct = "Нет: идемпотентность — про состояние сервера, а не про код ответа"
        d = ["Да: ответы на повтор обязаны совпадать", "Да: DELETE не идемпотентен по спецификации",
             "Нет: DELETE — безопасный метод"]
    else:
        stem = f'PATCH /{res}/{rid} с телом {{"op": "increment", "field": "{field}"}}. Идемпотентен ли такой запрос?'
        correct = "Нет: каждый повтор снова увеличит значение"
        d = ["Да: PATCH идемпотентен по спецификации", "Да: тело запроса при повторе одинаковое",
             "Нет: PATCH запрещено повторять по спецификации"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "Идемпотентны GET, HEAD, OPTIONS, PUT, DELETE: повтор не меняет итоговое состояние. POST и "
                       "PATCH в общем случае не идемпотентны. Безопасные методы (GET, HEAD, OPTIONS) не меняют состояние.",
    }


# --- Redis: структуры данных ----------------------------------------------------------------------
_REDIS_CASES = [
    ("Таблица лидеров: {n} игроков с очками, нужно быстро получать топ-{k}.", "Sorted Set: ZADD, ZREVRANGE",
     ["List: LPUSH, LRANGE", "Set: SADD, SMEMBERS", "String: SET, GET"]),
    ("Счётчик просмотров {thing}, который одновременно увеличивают {k} процессов.", "String и атомарный INCR",
     ["GET, затем SET значения + 1", "Hash: HGET, затем HSET", "Pub/Sub: PUBLISH на каждый просмотр"]),
    ("Очередь задач: продюсеры добавляют задачи, воркеры блокирующе ждут следующую.", "List: LPUSH + BRPOP",
     ["Set: SADD + SMEMBERS", "String: APPEND + GET", "Sorted Set: ZADD + ZCARD"]),
    ("Нужно хранить уникальные id посетителей {thing} за день и проверять, был ли конкретный id.",
     "Set: SADD, SISMEMBER", ["List: RPUSH, LINDEX", "String: APPEND, GETRANGE", "Pub/Sub: PUBLISH, SUBSCRIBE"]),
    ("Сессия пользователя с несколькими полями должна исчезнуть через {k} минут.", "Hash: HSET + EXPIRE",
     ["List: RPUSH без TTL", "Set: SADD + PERSIST", "Pub/Sub: PUBLISH в канал сессии"]),
    ("Нужно приближённо считать уникальных посетителей {thing} (~{n} в месяц) при минимуме памяти.",
     "HyperLogLog: PFADD, PFCOUNT", ["Set: SADD, SCARD", "List: RPUSH, LLEN", "String: INCR на каждый визит"]),
    ("Ограничение: не больше {k} запросов в минуту на пользователя (фиксированное окно).",
     "INCR ключа окна + EXPIRE 60", ["SET ключа без TTL на каждый запрос", "LPUSH в список без очистки и LLEN",
                                     "PUBLISH в канал на каждый запрос"]),
]


@template(id="backend.redis_types", pool="backend", topics=["redis"], fmt="concept", a=1.0, b=-0.4,
          title="Структуры данных Redis", variants=40)
def _redis_types(rng: random.Random) -> dict:
    case, correct, distractors = rng.choice(_REDIS_CASES)
    stem = case.format(thing=rng.choice(["страницы", "статьи", "товара", "видео"]),
                       n=rng.choice(["2 млн", "10 млн", "50 млн"]), k=rng.choice([10, 50, 100]))
    return {
        "stem": f"{stem} Какую структуру и команды Redis выбрать?",
        "correct": correct,
        "distractors": distractors,
        "explanation": "Sorted Set — рейтинги, INCR — атомарный счётчик, List + BRPOP — очередь, Set — уникальность, "
                       "Hash + EXPIRE — объект с TTL, HyperLogLog — приближённое число уникальных при ~12 КБ памяти.",
    }


# --- Docker: кэш слоёв -----------------------------------------------------------------------------
_STACKS = {
    "python": ("python:3.12-slim", "COPY requirements.txt .", "RUN pip install -r requirements.txt", None,
               'CMD ["python", "main.py"]', "requirements.txt", "app/handlers.py"),
    "node": ("node:20-alpine", "COPY package*.json ./", "RUN npm ci", None, 'CMD ["node", "server.js"]',
             "package.json", "src/routes.js"),
    "go": ("golang:1.22", "COPY go.mod go.sum ./", "RUN go mod download", "RUN go build -o /bin/app ./cmd/app",
           'CMD ["/bin/app"]', "go.mod", "internal/api/handler.go"),
}


@template(id="backend.docker_layers", pool="backend", topics=["docker"], fmt="concept", a=1.2, b=-0.2,
          title="Кэширование слоёв Docker", variants=24)
def _docker_layers(rng: random.Random) -> dict:
    stack = rng.choice(list(_STACKS))
    base, copy_deps, install, build, cmd, depfile, src = _STACKS[stack]
    good = rng.random() < 0.6
    lines = [f"FROM {base}", "WORKDIR /app"] + ([copy_deps, install, "COPY . ."] if good else ["COPY . .", install])
    if build:
        lines.append(build)
    lines.append(cmd)
    none_ = "Ни одна — все слои возьмутся из кэша"
    all_ = "Все инструкции — ведь Dockerfile изменился"

    def from_(instr: str) -> str:
        return f"Начиная с {instr} и все последующие"

    change = rng.choices(["src", "deps", "cmd", "ignored"], weights=[15, 35, 25, 25])[0]
    if change == "src":
        what = f"изменили файл {src}"
        correct = from_("COPY . .")
        d = ["Только COPY . .", from_(copy_deps) if good else f"COPY . . и далее, кроме {install}", none_]
    elif change == "deps":
        what = f"добавили новую зависимость в {depfile}"
        if good:
            correct, d = from_(copy_deps), [from_("COPY . ."), f"Только {install}", none_]
        else:
            correct, d = from_("COPY . ."), [from_(install), f"Только {install}", none_]
    elif change == "cmd":
        what = "в Dockerfile поменяли аргументы только у инструкции CMD"
        correct, d = "Только CMD — предыдущие слои из кэша", [all_, from_("COPY . ."), none_]
    else:
        what = "изменили файл docs/README.md, а в .dockerignore есть строка docs/"
        correct, d = none_, [from_("COPY . ."), "Только COPY . .", all_]
    return {
        "stem": f"Образ по этому Dockerfile уже собирался, кэш сборки на месте. Затем {what} и снова запустили "
                f"docker build. Какие инструкции выполнятся заново (не из кэша)?",
        "code": "\n".join(lines),
        "code_lang": "dockerfile",
        "correct": correct,
        "distractors": d,
        "explanation": "Кэш инвалидируется с первой инструкции, чьи входные данные изменились (для COPY — содержимое "
                       "копируемых файлов с учётом .dockerignore), и для всех инструкций после неё.",
    }


# --- asyncio: последовательное и параллельное ожидание ----------------------------------------------
@template(id="backend.async_gather_time", pool="backend", topics=["concurrency", "python"], fmt="calc", a=1.3, b=0.2,
          title="Конкурентность в asyncio", variants=2000)
def _async_gather_time(rng: random.Random) -> dict:
    for _ in range(300):
        kinds = [rng.choice(["seq", "gather", "gather", "task"]) for _ in range(rng.randint(2, 3))]
        if kinds.count("task") > 1 or all(k == "seq" for k in kinds):
            continue
        lines, durs, total, total_min, task_seq = [], [], 0, 0, 0
        for kd in kinds:
            if kd == "seq":
                d = rng.randint(1, 4)
                lines.append(f"    await job({d})")
                durs.append(d)
                total, total_min, task_seq = total + d, total_min + d, task_seq + d
            elif kd == "gather":
                ds = rng.sample(range(1, 6), rng.randint(2, 3))
                lines.append("    await asyncio.gather(" + ", ".join(f"job({d})" for d in ds) + ")")
                durs += ds
                total, total_min, task_seq = total + max(ds), total_min + min(ds), task_seq + max(ds)
            else:
                a, b = rng.sample(range(1, 6), 2)
                lines += [f"    t = asyncio.create_task(job({a}))", f"    await job({b})", "    await t"]
                durs += [a, b]
                total, total_min, task_seq = total + max(a, b), total_min + min(a, b), task_seq + a + b
        cands = [sum(durs), max(durs), total_min, task_seq]
        if len(set(cands) - {total}) >= 3:
            break
    code = ("import asyncio\n\nasync def job(sec):\n    await asyncio.sleep(sec)\n\nasync def main():\n"
            + "\n".join(lines) + "\n\nasyncio.run(main())")
    return {
        "stem": "Сколько секунд (примерно) выполняется программа?",
        "code": code,
        "code_lang": "python",
        "correct": _sec(total),
        "distractors": [_sec(c) for c in cands],
        "explanation": "await последовательно ждёт корутину; gather и заранее созданная задача (create_task) выполняются "
                       "конкурентно, поэтому шаг длится столько, сколько самая долгая из них.",
    }


# --- SQL: LEFT JOIN и условие в WHERE ---------------------------------------------------------------
@template(id="backend.sql_left_join", pool="backend", topics=["sql"], fmt="calc", a=1.4, b=0.6,
          title="LEFT JOIN: условие в ON и в WHERE", variants=2000)
def _sql_left_join(rng: random.Random) -> dict:
    names = rng.sample(_NAMES, 4)
    custs = list(enumerate(names, 1))
    for _ in range(500):
        orders = [(10 + j, rng.choice([1, 1, 2, 2, 3, 4, 9]), rng.choice(["paid", "new"]))
                  for j in range(rng.randint(4, 6))]
        cnt = {c: sum(o[1] == c for o in orders) for c, _ in custs}
        paid = {c: sum(o[1] == c and o[2] == "paid" for o in orders) for c, _ in custs}
        join_all = sum(max(1, v) for v in cnt.values())
        a_rows = sum(paid.values())
        b_rows = sum(max(1, v) for v in paid.values())
        c_rows = sum(v == 0 for v in cnt.values())
        kind = rng.randrange(3)
        if kind == 0:
            correct, cands = a_rows, [b_rows, join_all, len(orders), len(custs)]
        elif kind == 1:
            correct, cands = b_rows, [a_rows, join_all, len(custs), len(orders)]
        else:
            correct, cands = c_rows, [sum(v == 0 for v in paid.values()), len(custs) - c_rows, len(orders) - join_all
                                      + c_rows, c_rows + 1]
        cands = [c for c in cands if c >= 0]
        if len(set(cands) - {correct}) >= 3 and (kind != 2 or c_rows > 0 or rng.random() < 0.3):
            break
    data = ", ".join(f"({i}, {n})" for i, n in custs)
    o_parts = [f"({i}, {c}, {s})" for i, c, s in orders]
    o_lines = "\n".join("--   " + ", ".join(o_parts[k:k + 3]) for k in range(0, len(o_parts), 3))
    head = f"-- customers(id, name): {data}\n-- orders(id, customer_id, status):\n{o_lines}\n"
    if kind == 0:
        q = "SELECT c.name, o.id\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\nWHERE o.status = 'paid';"
    elif kind == 1:
        q = "SELECT c.name, o.id\nFROM customers c\nLEFT JOIN orders o\n  ON o.customer_id = c.id AND o.status = 'paid';"
    else:
        q = "SELECT c.name\nFROM customers c\nLEFT JOIN orders o ON o.customer_id = c.id\nWHERE o.id IS NULL;"
    return {
        "stem": "Сколько строк вернёт запрос?",
        "code": head + q,
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "Условие на правую таблицу в WHERE отбрасывает строки с NULL и превращает LEFT JOIN во "
                       "внутренний; то же условие в ON сохраняет всех клиентов (без пары — одна строка с NULL).",
    }


# --- Python: исключения и finally -------------------------------------------------------------------
_EXC_CASES = [  # (выражение, класс исключения, «чужой» класс, родительский класс, который его ловит)
    ('{}["k"]', "KeyError", "IndexError", "LookupError"),
    ("[1, 2][5]", "IndexError", "KeyError", "LookupError"),
    ('int("x")', "ValueError", "TypeError", "Exception"),
    ("1 / 0", "ZeroDivisionError", "ValueError", "ArithmeticError"),
    ("None + 1", "TypeError", "ValueError", "Exception"),
]


@template(id="backend.py_exceptions", pool="backend", topics=["python"], fmt="output", a=1.2, b=0.5,
          title="Исключения: try/except/else/finally", variants=2000, verify=True)
def _py_exceptions(rng: random.Random) -> dict:
    a, b, c, d, e = rng.sample(["start", "try", "ok", "done", "fail", "end", "begin", "clean", "boom", "step"], 5)
    kind = rng.randrange(3)
    if kind == 0:
        r = rng.choice(["R1", "result", "42", "value"])
        code = (f'def f():\n    try:\n        print("{a}", end=" ")\n        return "{r}"\n    finally:\n'
                f'        print("{b}", end=" ")\n\nprint(f())')
        correct, cands = f"{a} {b} {r}", [f"{a} {r} {b}", f"{a} {r}", f"{b} {a} {r}"]
        expl = "finally выполняется перед фактическим возвратом из функции, поэтому печатается раньше результата."
    elif kind == 1:
        n = rng.choice([17, 23, 29, 31])
        x = rng.choice([0, 0, 2, 3, 4])
        code = (f'def g(x):\n    try:\n        print("{a}", end=" ")\n        r = {n} // x\n'
                f'    except ZeroDivisionError:\n        print("{b}", end=" ")\n        r = -1\n'
                f'    else:\n        print("{c}", end=" ")\n    finally:\n        print("{d}", end=" ")\n'
                f'    return r\n\nprint(g({x}))')
        if x == 0:
            correct = f"{a} {b} {d} -1"
            cands = [f"{a} {b} {c} {d} -1", f"{a} {b} -1", f"{a} {b} {d}", f"{a} {d} -1"]
        else:
            correct = f"{a} {c} {d} {n // x}"
            cands = [f"{a} {d} {n // x}", f"{a} {c} {n // x}", f"{a} {c} {d} {n / x}", f"{a} {b} {c} {d} {n // x}"]
        expl = "else выполняется, только если в try не было исключения; finally — всегда, до return."
    else:
        expr, exc, wrong, parent = rng.choice(_EXC_CASES)
        caught = rng.random() < 0.35
        inner = parent if caught else wrong
        code = (f'try:\n    try:\n        print("{a}", end=" ")\n        {expr}\n        print("{b}", end=" ")\n'
                f'    except {inner}:\n        print("{c}", end=" ")\n    finally:\n        print("{d}", end=" ")\n'
                f'except {exc}:\n    print("{e}", end=" ")')
        if caught:
            correct, cands = f"{a} {c} {d}", [f"{a} {d} {e}", f"{a} {c} {d} {e}", f"{a} {b} {c} {d}"]
            expl = f"{exc} — подкласс {parent}, поэтому его ловит внутренний except; внешний уже не срабатывает."
        else:
            correct, cands = f"{a} {d} {e}", [f"{a} {c} {d}", f"{a} {d}", f"{a} {c} {d} {e}", f"{a} {b} {d} {e}"]
            expl = f"{exc} не подходит под except {wrong}: исключение выходит наружу, но finally выполняется до этого."
    return {"stem": "Что выведет этот код?", "code": code, "code_lang": "python", "correct": correct,
            "distractors": cands, "explanation": expl}


# --- Надёжность: повторы и идемпотентность -----------------------------------------------------------
@template(id="backend.retry_idempotency", pool="backend", topics=["system_design", "microservices", "rest"],
          fmt="concept", a=1.2, b=0.7, title="Повторы, идемпотентность и отказоустойчивость", variants=25)
def _retry_idempotency(rng: random.Random) -> dict:
    amount = rng.choice([490, 1200, 2500, 15000])
    n = rng.choice([500, 2000, 10000])
    t = rng.choice([5, 10, 30])
    entity = rng.choice(["заказ", "платёж", "профиль пользователя", "бронирование"])
    kind = rng.randrange(5)
    if kind == 0:
        stem = (f"Приложение отправило POST /payments на {amount} ₽, получило таймаут через {t} с и повторило запрос. "
                f"Как гарантировать, что деньги спишутся один раз?")
        correct = "Ключ идемпотентности (Idempotency-Key), сервер хранит результат по ключу"
        d = ["Повторять запрос с экспоненциальной задержкой", "Заменить POST на GET с параметрами в URL",
             f"Увеличить таймаут клиента до {t * 6} с"]
    elif kind == 1:
        stem = (f"Консьюмер читает события из очереди с доставкой at-least-once и начисляет по {amount} бонусов. "
                f"Как избежать двойного начисления?")
        correct = "Дедупликация по id события в той же транзакции, что и начисление"
        d = ["Подтверждать (ack) сообщение до обработки", "Увеличить число консьюмеров",
             "Обрабатывать каждое сообщение дважды и сравнивать результат"]
    elif kind == 2:
        stem = (f"{n} клиентов одновременно получили 503 и повторяют запрос ровно через 1 с. Сервис не может "
                f"подняться под этой нагрузкой. Что изменить в клиентах?")
        correct = "Экспоненциальная задержка между повторами со случайным джиттером"
        d = ["Повторять сразу, без задержки", "Уменьшить фиксированную задержку до 100 мс",
             "Повторять бесконечно до успеха"]
    elif kind == 3:
        stem = (f"Сервис A вызывает сервис B; B деградировал и отвечает за {t} с. Повторы из A добивают B, а потоки A "
                f"заняты ожиданием. Какой паттерн нужен в A?")
        correct = "Circuit breaker: при серии ошибок временно не вызывать B"
        d = [f"Увеличить число повторов до {t}", "Убрать таймауты на вызовах B", "Вызывать B синхронно в цикле до успеха"]
    else:
        stem = (f"Нужно сохранить {entity} в БД и опубликовать событие в брокер сообщений; при падении между этими "
                f"шагами событие теряется. Какой подход надёжен?")
        correct = "Transactional outbox: событие пишется в таблицу в той же транзакции"
        d = ["Сначала опубликовать событие, затем закоммитить БД", "Обернуть оба шага в try/except с логированием",
             "Публиковать событие из отдельного потока без ожидания"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "Повторы безопасны только для идемпотентных операций (ключ идемпотентности, дедупликация по id). "
                       "Нагрузку от повторов гасят backoff с джиттером и circuit breaker; атомарность БД + событие — outbox.",
    }


# --- Python: GIL, потоки и процессы -----------------------------------------------------------------
@template(id="backend.py_gil", pool="backend", topics=["concurrency", "python"], fmt="calc", a=1.2, b=0.8,
          title="GIL: потоки, процессы, asyncio", variants=100)
def _py_gil(rng: random.Random) -> dict:
    cores = rng.choice([4, 8])
    t = rng.choice([1, 2, 3, 5])
    kind = rng.randrange(5)
    if kind == 0:
        n = rng.choice([4, 8])
        desc = f"{n} задач по {t} с чистых вычислений на Python запускают через ThreadPoolExecutor(max_workers={n})"
        correct = n * t
    elif kind == 1:
        m = rng.choice([1, 2])
        n = cores * m
        desc = f"{n} задач по {t} с чистых вычислений на Python запускают через ProcessPoolExecutor(max_workers={cores})"
        correct = m * t
    elif kind == 2:
        n = rng.choice([4, 8, 16])
        desc = (f"{n} задач, каждая {t} с ждёт ответа внешнего HTTP-сервиса, запускают через "
                f"ThreadPoolExecutor(max_workers={n})")
        correct = t
    elif kind == 3:
        w = rng.choice([2, 4])
        n = w * rng.choice([2, 3, 4])
        desc = f"{n} задач, каждая {t} с ждёт ответа сети, запускают через ThreadPoolExecutor(max_workers={w})"
        correct = n // w * t
    else:
        n = rng.choice([4, 8])
        desc = f"{n} корутин, каждая {t} с выполняет вычисления на Python без единого await, запускают через asyncio.gather"
        correct = n * t
    cands = [n * t, t, math.ceil(n / cores) * t, 2 * t, n * t // 2, cores * t, 2 * n * t]
    return {
        "stem": f"CPython в стандартной сборке (с GIL), машина с {cores} ядрами. {desc}. "
                f"Сколько примерно займёт выполнение всех задач?",
        "correct": _sec(correct),
        "distractors": [_sec(c) for c in cands if c != correct],
        "explanation": "GIL не даёт потокам параллельно исполнять байткод: CPU-bound задачи в потоках и в корутинах без "
                       "await идут по очереди. Процессы используют разные ядра; на I/O потоки отпускают GIL и ждут параллельно.",
    }


# --- SQL: оконные функции ---------------------------------------------------------------------------
@template(id="backend.sql_window", pool="backend", topics=["sql", "postgresql"], fmt="calc", a=1.3, b=1.0,
          title="Оконные функции SQL", variants=2000)
def _sql_window(rng: random.Random) -> dict:
    names = rng.sample(_NAMES, 7)
    depts = rng.choice([("dev", "ops"), ("sales", "support"), ("backend", "frontend")])
    for _ in range(1000):
        vals = rng.sample(range(100, 301, 20), 4)
        rows = [(nm, rng.choice(depts), rng.choice(vals)) for nm in names]
        kind = rng.randrange(4)
        sal = [r[2] for r in rows]
        if kind in (0, 1):
            tgt = rng.choice(rows)
            ts = tgt[2]
            above = [s for s in sal if s > ts]
            rank, dense, last = 1 + len(above), 1 + len(set(above)), sum(s >= ts for s in sal)
            if len(above) < 2 or len(set(above)) == len(above):
                continue
            func = "RANK()" if kind == 0 else "DENSE_RANK()"
            correct = rank if kind == 0 else dense
            cands = [dense, last, rank + 1] if kind == 0 else [rank, last, dense + 1]
            inner = f"  SELECT name, {func} OVER (ORDER BY salary DESC) AS r\n  FROM employees"
            q = f"SELECT r FROM (\n{inner}\n) t WHERE name = '{tgt[0]}';"
        elif kind == 2:
            tgt = rng.choice(rows)
            same = [r for r in rows if r[1] == tgt[1]]
            ts = tgt[2]
            if sum(r[2] == ts for r in same) < 2:
                continue
            correct = sum(r[2] for r in same if r[2] <= ts)
            less = sum(r[2] for r in same if r[2] < ts)
            cands = [less + ts, sum(r[2] for r in same), sum(s for s in sal if s <= ts), less]
            q = (f"SELECT s FROM (\n  SELECT name, SUM(salary) OVER (\n    PARTITION BY dept ORDER BY salary) AS s\n"
                 f"  FROM employees\n) t WHERE name = '{tgt[0]}';")
        else:
            k = rng.choice([1, 2, 3])
            func = rng.choice(["ROW_NUMBER", "RANK", "DENSE_RANK"])
            cnt = {"ROW_NUMBER": 0, "RANK": 0, "DENSE_RANK": 0}
            for dp in depts:
                ss = [r[2] for r in rows if r[1] == dp]
                cnt["ROW_NUMBER"] += min(k, len(ss))
                cnt["RANK"] += sum(1 + sum(o > s for o in ss) <= k for s in ss)
                cnt["DENSE_RANK"] += sum(1 + len({o for o in ss if o > s}) <= k for s in ss)
            correct = cnt[func]
            if sum(v == correct for v in cnt.values()) > 1:  # функции должны давать разные ответы
                continue
            cands = [v for f, v in cnt.items() if f != func] + [k, k * len(depts) + 1, len(rows)]
            q = (f"SELECT COUNT(*) FROM (\n  SELECT {func}() OVER (\n    PARTITION BY dept ORDER BY salary DESC) AS rn\n"
                 f"  FROM employees\n) t WHERE rn <= {k};")
        if len(set(cands) - {correct}) >= 3:
            break
    table = "\n".join(f"-- {n:<5} | {d} | {s}" for n, d, s in rows)
    return {
        "stem": "Какое значение вернёт запрос?",
        "code": f"-- employees\n-- name | dept | salary\n{table}\n{q}",
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "RANK оставляет пропуски после равных значений, DENSE_RANK — нет, ROW_NUMBER нумерует без учёта "
                       "равенства. Накопительный SUM с ORDER BY по умолчанию (RANGE) включает все строки с равным ключом.",
    }


# --- Кэширование: типовые проблемы ------------------------------------------------------------------
@template(id="backend.cache_problems", pool="backend", topics=["redis", "system_design"], fmt="concept", a=1.2, b=1.2,
          title="Проблемы кэширования под нагрузкой", variants=500)
def _cache_problems(rng: random.Random) -> dict:
    key = rng.choice([f"product:{rng.randint(1, 999)}", "feed:main", "rates:usd", "config:all", "top:sellers"])
    ttl = rng.choice([30, 60, 300, 600])
    rps = rng.choice([2000, 5000, 10000, 20000])
    ms = rng.choice([200, 500, 800, 1500])
    kind = rng.randrange(5)
    if kind == 0:
        stem = (f"Ключ {key} читают {rps} раз/с, TTL = {ttl} с, пересчёт значения из БД занимает {ms} мс. В момент "
                f"истечения TTL сотни запросов одновременно идут в БД. Что решает проблему?")
        correct = "Блокировка на пересчёт (single-flight), остальным — старое значение"
        d = ["Уменьшить TTL ключа", "Увеличить пул соединений к БД", "Удалять ключ из кэша при каждом чтении"]
    elif kind == 1:
        stem = (f"После прогрева в кэш записали {rps} ключей с одинаковым TTL {ttl} с. Ровно через {ttl} с нагрузка "
                f"на БД резко скачет. Что сделать?")
        correct = "Добавить к TTL случайный джиттер"
        d = ["Уменьшить TTL всем ключам вдвое", "Увеличить TTL всем ключам на одну и ту же величину",
             "Прогревать кэш чаще с тем же TTL"]
    elif kind == 2:
        stem = (f"Боты запрашивают товары с несуществующими id (~{rps} запросов/с). Каждый такой запрос промахивается "
                f"мимо кэша и идёт в БД. Что поможет?")
        correct = "Кэшировать «пустой» ответ с коротким TTL или Bloom-фильтр"
        d = ["Увеличить TTL существующих ключей", "Добавить ещё одну реплику кэша", "Отключить кэш для запросов по id"]
    elif kind == 3:
        stem = f"Один ключ {key} читают {rps * 10} раз/с, и шард Redis с этим ключом упирается в CPU. Что поможет?"
        correct = "Локальный кэш в процессе или копии ключа на разных шардах"
        d = ["Уменьшить TTL этого ключа", "Удалять ключ после каждого чтения", "Увеличить maxmemory на этом шарде"]
    else:
        stem = f"Схема cache-aside для {key}: при изменении данных сначала пишем в БД. Что безопаснее сделать затем?"
        correct = "Удалить ключ из кэша (инвалидировать)"
        d = [f"Ничего: значение само обновится через {ttl} с по TTL", "Записать в кэш значение, прочитанное до изменения",
             "Ничего: кэш нужно было обновить до записи в БД"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "Stampede — single-flight/stale-while-revalidate; массовое истечение — джиттер TTL; промахи по "
                       "несуществующим ключам — negative caching/Bloom-фильтр; горячий ключ — локальный кэш или шардирование.",
    }


# --- asyncio: блокирующий вызов в корутине ------------------------------------------------------------
@template(id="backend.asyncio_blocking", pool="backend", topics=["concurrency", "python"], fmt="calc", a=1.4, b=1.3,
          title="Блокирующие вызовы в event loop", variants=2000)
def _asyncio_blocking(rng: random.Random) -> dict:
    for _ in range(500):
        tasks = [(rng.choice(["fetch", "compute"]), rng.randint(1, 4)) for _ in range(rng.randint(3, 4))]
        kinds = {k for k, _ in tasks}
        if kinds != {"fetch", "compute"}:
            continue
        clock, ends = 0, []
        for k, d in tasks:  # задачи стартуют по порядку; блокирующий sleep останавливает весь event loop
            if k == "compute":
                clock += d
                ends.append(clock)
            else:
                ends.append(clock + d)
        correct = max(ends)
        block = sum(d for k, d in tasks if k == "compute")
        max_async = max(d for k, d in tasks if k == "fetch")
        cands = [sum(d for _, d in tasks), max(d for _, d in tasks), block + max_async, max(block, max_async)]
        if len(set(cands) - {correct}) >= 3:
            break
    calls = ", ".join(f"{k}({d})" for k, d in tasks)
    code = ("import asyncio\nimport time\n\nasync def fetch(sec):\n    await asyncio.sleep(sec)\n\n"
            "async def compute(sec):\n    time.sleep(sec)\n\nasync def main():\n"
            f"    await asyncio.gather({calls})\n\nasyncio.run(main())")
    return {
        "stem": "Сколько секунд (примерно) выполняется программа?",
        "code": code,
        "code_lang": "python",
        "correct": _sec(correct),
        "distractors": [_sec(c) for c in cands],
        "explanation": "Задачи gather стартуют по порядку. time.sleep блокирует весь event loop, поэтому таймеры "
                       "asyncio.sleep у следующих задач запускаются только после него; итог — max(старт + длительность).",
    }


# --- Kafka: партиции, группы, семантика доставки ----------------------------------------------------
@template(id="backend.kafka_semantics", pool="backend", topics=["kafka", "microservices"], fmt="concept", a=1.3, b=1.4,
          title="Kafka: порядок и гарантии доставки", variants=150)
def _kafka_semantics(rng: random.Random) -> dict:
    topic = rng.choice(["orders", "payments", "clicks", "events", "audit"])
    p = rng.choice([3, 4, 6, 8, 12])
    c = p + rng.randint(1, 4)
    kind = rng.randrange(7)
    if kind == 0:
        stem = (f"Топик {topic} имеет {p} партиций. В одной consumer group запущено {c} консьюмеров. "
                f"Сколько из них не получат ни одной партиции?")
        correct, d = str(c - p), ["0", str(c), str(p), str(c - p + 1)]
    elif kind == 1:
        stem = f"Продюсер пишет события в топик {topic} ({p} партиций) с ключом user_id. Что Kafka гарантирует о порядке?"
        correct = "Порядок внутри партиции, а значит для событий одного ключа"
        d = ["Глобальный порядок по всему топику", "Никакого порядка, даже внутри партиции",
             "Порядок по времени создания на продюсере для всех ключей"]
    elif kind == 2:
        stem = f"Число партиций топика {topic} увеличили с {p} до {2 * p}. Что будет с событиями одного ключа?"
        correct = "Новые события ключа могут уйти в другую партицию: порядок нарушится"
        d = ["Kafka перераспределит старые сообщения по новым партициям",
             "Ничего: ключ навсегда закреплён за своей партицией", "Запись в топик блокируется до ручной ребалансировки"]
    elif kind == 3:
        stem = f"Две разные consumer group (analytics и billing) подписаны на топик {topic}. Сколько раз прочитают сообщение?"
        correct = "По одному разу в каждой группе — всего 2"
        d = ["Один раз: группы делят сообщения между собой", f"{p} раз — по числу партиций",
             "Один раз, если у групп одинаковое число консьюмеров"]
    elif kind == 4:
        stem = (f"Консьюмер топика {topic} коммитит offset сразу после получения сообщения, до обработки, и падает "
                f"посреди обработки. Какая семантика доставки получается?")
        correct = "At-most-once: сообщение может быть потеряно"
        d = ["At-least-once: сообщение обработается повторно", "Exactly-once", "Kafka сама откатит offset назад"]
    elif kind == 5:
        stem = (f"Консьюмер топика {topic} пишет результат в БД и только потом коммитит offset. Он упал между "
                f"записью в БД и коммитом. Что произойдёт?")
        correct = "После рестарта сообщение обработается повторно (at-least-once)"
        d = ["Сообщение будет потеряно", "Kafka откатит запись в БД", "Будет exactly-once без доп. настроек"]
    else:
        stem = (f"В сервисе включены транзакции Kafka (exactly-once). На каждое сообщение из {topic} он отправляет "
                f"email. Гарантировано ли ровно одно письмо на сообщение?")
        correct = "Нет: EOS покрывает чтение-запись внутри Kafka, не внешние эффекты"
        d = ["Да, при isolation.level=read_committed", "Да, если enable.idempotence=true",
             "Да, если коммитить offset синхронно"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "Партиция — единица порядка и параллелизма: в группе одну партицию читает один консьюмер, разные "
                       "группы читают независимо. Ключ → партиция по хешу от числа партиций. Коммит до обработки — "
                       "at-most-once, после — at-least-once; exactly-once Kafka не распространяется на внешние системы.",
    }


# --- Транзакции: аномалии и уровни изоляции -----------------------------------------------------------
_ANOM = {"dirty": "Грязное чтение (dirty read)", "nonrep": "Неповторяющееся чтение (non-repeatable read)",
         "phantom": "Фантомное чтение (phantom read)", "lost": "Потерянное обновление (lost update)",
         "skew": "Аномалия записи (write skew)"}


@template(id="backend.isolation_anomalies", pool="backend", topics=["postgresql", "sql", "concurrency"],
          fmt="concept", a=1.4, b=1.6, title="Уровни изоляции транзакций", variants=1000)
def _isolation_anomalies(rng: random.Random) -> dict:
    tbl = rng.choice(["accounts", "wallets", "balances"])
    rid = rng.randint(1, 99)
    v1 = rng.choice(range(100, 1000, 50))
    v2 = v1 + rng.choice([50, 100, 150])
    status = rng.choice(["new", "pending", "open"])
    c1 = rng.randint(3, 9)
    kind = rng.randrange(6)
    sel = f"SELECT balance FROM {tbl} WHERE id = {rid};"
    cnt = f"SELECT COUNT(*) FROM orders WHERE status = '{status}';"
    if kind == 0:
        code = (f"-- PostgreSQL, READ COMMITTED\nT1: BEGIN;\nT1: {sel}  -- {v1}\n"
                f"T2: BEGIN;\nT2: UPDATE {tbl} SET balance = {v2} WHERE id = {rid};\nT2: COMMIT;\n"
                f"T1: {sel}  -- {v2}\nT1: COMMIT;")
        stem, correct = "Как называется аномалия, которую наблюдает T1?", _ANOM["nonrep"]
        d = [_ANOM["dirty"], _ANOM["phantom"], _ANOM["lost"]]
    elif kind == 1:
        code = (f"-- PostgreSQL, READ COMMITTED\nT1: BEGIN;\nT1: {cnt}  -- {c1}\n"
                f"T2: BEGIN;\nT2: INSERT INTO orders (status) VALUES ('{status}');\nT2: COMMIT;\n"
                f"T1: {cnt}  -- {c1 + 1}\nT1: COMMIT;")
        stem, correct = "Как называется аномалия, которую наблюдает T1?", _ANOM["phantom"]
        d = [_ANOM["nonrep"], _ANOM["dirty"], _ANOM["skew"]]
    elif kind == 2:
        s = rng.randint(5, 40)
        code = (f"-- PostgreSQL, READ COMMITTED; оба покупателя берут товар id = {rid}\n"
                f"T1: BEGIN;\nT2: BEGIN;\n"
                f"T1: SELECT stock FROM products WHERE id = {rid};  -- {s}\n"
                f"T2: SELECT stock FROM products WHERE id = {rid};  -- {s}\n"
                f"T1: UPDATE products SET stock = {s - 1} WHERE id = {rid}; COMMIT;\n"
                f"T2: UPDATE products SET stock = {s - 1} WHERE id = {rid}; COMMIT;")
        stem = "Продано 2 единицы, а stock уменьшился на 1. Как называется аномалия?"
        correct, d = _ANOM["lost"], [_ANOM["nonrep"], _ANOM["phantom"], _ANOM["dirty"]]
    elif kind == 3:
        a, b = rng.sample(["anna", "boris", "vera", "gleb", "dina"], 2)
        code = (f"-- Правило: должен остаться хотя бы один дежурный. Сейчас дежурят {a} и {b}.\n"
                f"-- Обе транзакции: PostgreSQL, REPEATABLE READ\n"
                f"T1: SELECT COUNT(*) FROM duty WHERE on_call;  -- 2\n"
                f"T2: SELECT COUNT(*) FROM duty WHERE on_call;  -- 2\n"
                f"T1: UPDATE duty SET on_call = false WHERE name = '{a}'; COMMIT;\n"
                f"T2: UPDATE duty SET on_call = false WHERE name = '{b}'; COMMIT;")
        stem = ("Обе транзакции успешно завершились, дежурных не осталось. Какой минимальный уровень изоляции "
                "PostgreSQL не допустит такого исхода?")
        correct, d = "SERIALIZABLE", ["REPEATABLE READ", "READ COMMITTED", "Никакой: изоляция тут не поможет"]
    elif kind == 4:
        code = (f"T1: BEGIN ISOLATION LEVEL REPEATABLE READ;\nT1: {cnt}  -- {c1}\n"
                f"T2: INSERT INTO orders (status) VALUES ('{status}');  -- autocommit\n"
                f"T1: {cnt}  -- ?")
        stem = "Что вернёт второй SELECT в T1 (PostgreSQL)?"
        correct, d = str(c1), [str(c1 + 1), "Ошибку сериализации", "Запрос будет ждать окончания T2"]
    else:
        code = (f"-- исходно balance = {v1}\nT1: BEGIN ISOLATION LEVEL READ UNCOMMITTED;\nT2: BEGIN;\n"
                f"T2: UPDATE {tbl} SET balance = {v2} WHERE id = {rid};  -- без COMMIT\nT1: {sel}  -- ?")
        stem = "Что увидит T1 в PostgreSQL?"
        correct, d = str(v1), [str(v2), "Запрос будет ждать окончания T2", "Ошибку: уровень не поддерживается"]
    return {
        "stem": stem,
        "code": code,
        "code_lang": "sql",
        "correct": correct,
        "distractors": d,
        "explanation": "READ COMMITTED видит коммиты других транзакций между запросами (неповторяющееся и фантомное "
                       "чтение). REPEATABLE READ в PostgreSQL работает по снимку и не видит фантомов, но допускает "
                       "write skew — его исключает только SERIALIZABLE. READ UNCOMMITTED в PostgreSQL = READ COMMITTED.",
    }


# --- Транзакции: конкурентное списание в PostgreSQL ---------------------------------------------------
@template(id="backend.pg_concurrent_update", pool="backend", topics=["postgresql", "concurrency", "sql"], fmt="calc",
          a=1.3, b=2.0, title="Конкурентные UPDATE и блокировки в PostgreSQL", variants=2000)
def _pg_concurrent_update(rng: random.Random) -> dict:
    kind = rng.choices(["rc_atomic", "rc_rmw", "rc_for_update", "rr_atomic", "rc_conditional", "rr_rmw"],
                       weights=[20, 10, 20, 20, 15, 15])[0]
    rid = rng.randint(1, 99)
    if kind == "rc_conditional":
        while True:
            bal = rng.choice(range(100, 501, 50))
            x1, x2 = rng.sample(range(30, bal + 1, 10), 2)
            if x1 + x2 > bal:
                break
    else:
        bal = rng.choice(range(1000, 3001, 100))
        x1, x2 = rng.sample(range(50, 401, 10), 2)
    level = "REPEATABLE READ" if kind.startswith("rr") else "READ COMMITTED"
    sel = f"SELECT balance FROM accounts WHERE id = {rid}"
    lines = [f"-- PostgreSQL; исходно balance = {bal}", f"T1: BEGIN ISOLATION LEVEL {level};",
             f"T2: BEGIN ISOLATION LEVEL {level};"]
    if kind in ("rc_atomic", "rr_atomic"):
        lines += [f"T1: UPDATE accounts SET balance = balance - {x1} WHERE id = {rid};",
                  f"T2: UPDATE accounts SET balance = balance - {x2} WHERE id = {rid};",
                  "T1: COMMIT;", "T2: COMMIT;"]
        correct = bal - x1 - x2 if kind == "rc_atomic" else bal - x1
    elif kind in ("rc_rmw", "rr_rmw"):
        lines += [f"T1: {sel};  -- {bal}", f"T2: {sel};  -- {bal}",
                  f"T1: UPDATE accounts SET balance = {bal - x1} WHERE id = {rid};  -- {bal} - {x1}", "T1: COMMIT;",
                  f"T2: UPDATE accounts SET balance = {bal - x2} WHERE id = {rid};  -- {bal} - {x2}", "T2: COMMIT;"]
        correct = bal - x2 if kind == "rc_rmw" else bal - x1
    elif kind == "rc_for_update":
        lines += [f"T1: {sel} FOR UPDATE;  -- {bal}", f"T2: {sel} FOR UPDATE;",
                  f"T1: UPDATE accounts SET balance = <прочитанное> - {x1} WHERE id = {rid};", "T1: COMMIT;",
                  f"T2: UPDATE accounts SET balance = <прочитанное> - {x2} WHERE id = {rid};", "T2: COMMIT;"]
        correct = bal - x1 - x2
    else:
        lines += [f"T1: UPDATE accounts SET balance = balance - {x1}\n      WHERE id = {rid} AND balance >= {x1};",
                  f"T2: UPDATE accounts SET balance = balance - {x2}\n      WHERE id = {rid} AND balance >= {x2};",
                  "T1: COMMIT;", "T2: COMMIT;"]
        correct = bal - x1
    cands = [bal - x1 - x2, bal - x1, bal - x2, bal]
    return {
        "stem": "Чему будет равен balance после завершения обеих транзакций? Транзакцию, получившую ошибку, "
                "не повторяют.",
        "code": "\n".join(lines),
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands if c != correct],
        "explanation": "В READ COMMITTED второй UPDATE ждёт блокировку строки, затем перечитывает её новую версию и "
                       "заново проверяет WHERE; SELECT … FOR UPDATE тоже вернёт новую версию. Запись значения, "
                       "вычисленного в приложении, теряет чужое обновление. В REPEATABLE READ изменение строки, "
                       "обновлённой параллельной транзакцией, падает с ошибкой сериализации.",
    }
