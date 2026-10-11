"""Общий пул шаблонов (core): базовые знания, общие для всех специализаций.

Каждый шаблон регистрируется декоратором @template (см. base.py).
"""
import ipaddress
import random

from app.services.bank.base import template


def _num(n: int) -> str:
    """Число с пробелами между разрядами: 1 048 576."""
    return f"{n:,}".replace(",", " ")


@template(id="core.py_slice", pool="core", topics=["python"], fmt="output", a=1.1, b=-1.8,
          title="Срез списка в Python", variants=2000, verify=True)
def _py_slice(rng: random.Random) -> dict:
    # Эталонный шаблон: параметры — имя переменной, содержимое списка, границы и шаг среза.
    name = rng.choice(["items", "data", "values", "nums", "arr"])
    xs = rng.sample(range(1, 60), 7)
    start = rng.randint(1, 3)
    stop = start + rng.randint(3, 4)  # срез не короче 3 элементов, чтобы дистракторы были различимы
    step = rng.choice([1, 2])
    correct = xs[start:stop:step]
    distractors = [xs[start:stop + 1:step], xs[start + 1:stop:step], xs[start:stop:3 - step] if step == 1 else xs[start:stop],
                   xs[start - 1:stop:step], list(reversed(correct)), xs[start:stop - 1:step]]
    code = f"{name} = {xs}\nprint({name}[{start}:{stop}:{step}])" if step != 1 else f"{name} = {xs}\nprint({name}[{start}:{stop}])"
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(d) for d in distractors],
        "explanation": "Срез берёт элементы с индекса start включительно до stop не включительно с шагом step.",
    }


# --- HTTP: коды ответов -------------------------------------------------------------------------------
_HTTP_CASES = [
    ("Клиент запрашивает GET /api/{res}/{id}, но объекта с таким id нет.", "404", ["400", "403", "500", "204"]),
    ("Запрос к защищённому GET /api/{res} пришёл без токена авторизации.", "401", ["403", "400", "404"]),
    ("Пользователь вошёл в систему, но у него нет прав на изменение /api/{res}/{id}.", "403", ["401", "400", "409"]),
    ("POST /api/{res} успешно создал новый объект с id={id}.", "201", ["202", "204", "302"]),
    ("DELETE /api/{res}/{id} выполнен успешно, тело ответа пустое.", "204", ["201", "202", "304"]),
    ("Клиент превысил лимит запросов к /api/{res} (rate limit).", "429", ["403", "503", "413"]),
    ("Тело запроса POST /api/{res} — синтаксически неверный JSON.", "400", ["401", "404", "500"]),
    ("Ресурс /api/{res} навсегда переехал на /api/v2/{res}.", "301", ["302", "304", "307"]),
    ("В обработчике GET /api/{res}/{id} возникло необработанное исключение.", "500", ["400", "502", "404"]),
    ("Клиент прислал If-None-Match с актуальным ETag, объект /api/{res}/{id} не менялся.", "304", ["200", "204", "302"]),
]


@template(id="core.http_status", pool="core", topics=["http"], fmt="concept", a=1.0, b=-1.4,
          title="Коды ответов HTTP", variants=300)
def _http_status(rng: random.Random) -> dict:
    case, correct, distractors = rng.choice(_HTTP_CASES)
    res = rng.choice(["orders", "users", "products", "invoices", "tickets", "reports"])
    stem = case.format(res=res, id=rng.randint(2, 999))
    return {
        "stem": f"{stem} Какой код ответа HTTP здесь наиболее уместен?",
        "correct": correct,
        "distractors": distractors,
        "explanation": "2xx — успех (201 Created, 204 No Content), 3xx — перенаправления и кэш (301, 304), "
                       "4xx — ошибка клиента (400, 401 без аутентификации, 403 нет прав, 404, 429), 5xx — ошибка сервера.",
    }


# --- Python: циклы и range ------------------------------------------------------------------------------
@template(id="core.py_loop_accum", pool="core", topics=["python"], fmt="output", a=1.1, b=-1.3,
          title="Циклы и range в Python", variants=1500, verify=True)
def _py_loop_accum(rng: random.Random) -> dict:
    v = rng.choice(["i", "n", "k", "x"])
    m = rng.choice([2, 3, 4, 5])
    if rng.random() < 0.5:
        acc = rng.choice(["total", "acc", "s", "result"])
        lo = m * rng.randint(1, 3)
        hi = lo + m * rng.randint(3, 5)  # обе границы кратны m: ошибка «включил stop» или «пропустил start» меняет ответ
        xs = range(lo, hi)
        correct = sum(x for x in xs if x % m == 0)
        cands = [correct + hi, correct - lo, correct + hi - lo, sum(xs), sum(x for x in xs if x % m)]
        code = f"{acc} = 0\nfor {v} in range({lo}, {hi}):\n    if {v} % {m} == 0:\n        {acc} += {v}\nprint({acc})"
        expl = f"range({lo}, {hi}) не включает {hi}; суммируются кратные {m} числа от {lo} до {hi - 1}."
    else:
        acc = rng.choice(["count", "cnt", "c"])
        step = rng.choice([2, 3])
        lo = rng.randint(0, 4)
        hi = lo + step * rng.randint(4, 7)
        xs = range(lo, hi, step)
        correct = sum(1 for x in xs if x % m)
        cands = [c for c in (len(xs) - correct, len(xs), correct + 1, correct - 1, correct + 2) if c >= 0]
        code = (f"{acc} = 0\nfor {v} in range({lo}, {hi}, {step}):\n    if {v} % {m} == 0:\n        continue\n"
                f"    {acc} += 1\nprint({acc})")
        expl = f"Перебираются {list(xs)}; continue пропускает кратные {m}, остальные считаются."
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": expl,
    }


# --- Структуры данных: выбор под задачу ------------------------------------------------------------------
_STACK, _QUEUE, _SET = "Стек (LIFO)", "Очередь (FIFO)", "Хеш-множество (set)"
_HEAP, _TRIE, _BST = "Двоичная куча (приоритетная очередь)", "Префиксное дерево (trie)", "Сбалансированное дерево поиска"
_LRU, _LIST, _SARR = "Хеш-таблица + двусвязный список", "Односвязный список", "Отсортированный массив"
_DS_CASES = [
    ("Редактор {ent} должен поддерживать отмену: отменяется последнее выполненное действие.", _STACK, [_QUEUE, _SET, _HEAP]),
    ("Заявки на обработку {ent} нужно обслуживать строго в порядке поступления.", _QUEUE, [_STACK, _HEAP, _BST]),
    ("Среди {n} {ent} нужно в среднем за O(1) проверять, встречался ли уже данный id.", _SET, [_SARR, _LIST, _STACK]),
    ("Поток из {n} {ent}: нужно часто добавлять элементы и каждый раз извлекать самый приоритетный.", _HEAP, [_SET, _QUEUE, _LIST]),
    ("Автодополнение: по введённому префиксу найти все названия {ent} (всего {n}).", _TRIE, [_SET, _HEAP, _STACK]),
    ("{n} {ent} хранятся упорядоченно; частые вставки и запросы «все ключи в диапазоне [x; y]».", _BST, [_SET, _HEAP, _QUEUE]),
    ("Кэш на {n} {ent} с вытеснением давно не использованных (LRU), get и put за O(1).", _LRU, [_HEAP, _SARR, _STACK]),
    ("Обход графа связей {ent} в ширину (BFS), чтобы найти кратчайший путь по числу рёбер.", _QUEUE, [_STACK, _HEAP, _TRIE]),
]


@template(id="core.ds_choice", pool="core", topics=["data_structures"], fmt="concept", a=1.0, b=-0.9,
          title="Выбор структуры данных", variants=150)
def _ds_choice(rng: random.Random) -> dict:
    case, correct, distractors = rng.choice(_DS_CASES)
    ent = rng.choice(["заказов", "пользователей", "товаров", "документов", "сообщений", "задач"])
    stem = case.format(ent=ent, n=_num(rng.choice([10_000, 50_000, 100_000, 1_000_000, 5_000_000])))
    return {
        "stem": f"{stem} Какая структура данных подходит лучше всего?",
        "correct": correct,
        "distractors": distractors,
        "explanation": "Стек — LIFO, очередь — FIFO (и BFS), set — проверка принадлежности за O(1), куча — извлечение "
                       "максимума за O(log n), trie — поиск по префиксу, сбалансированное дерево — порядок и диапазоны, "
                       "LRU — хеш-таблица + двусвязный список.",
    }


# --- Linux: права доступа -----------------------------------------------------------------------------
def _rwx(d: int) -> str:
    return ("r" if d & 4 else "-") + ("w" if d & 2 else "-") + ("x" if d & 1 else "-")


def _rev_bits(d: int) -> int:
    return ((d & 1) << 2) | (d & 2) | ((d & 4) >> 2)


@template(id="core.linux_chmod", pool="core", topics=["linux"], fmt="calc", a=1.2, b=-0.7,
          title="Права доступа в Linux", variants=150)
def _linux_chmod(rng: random.Random) -> dict:
    while True:
        o, g, t = rng.choice([7, 6, 5, 4]), rng.choice([7, 6, 5, 4, 0]), rng.choice([5, 4, 1, 0])
        if o != t:  # иначе перестановка «владелец ↔ остальные» не отличалась бы от верного ответа
            break
    fname = rng.choice(["deploy.sh", "backup.py", "config.yaml", "run.sh", "report.csv"])

    def perm(a: int, b: int, c: int) -> str:
        return "-" + _rwx(a) + _rwx(b) + _rwx(c)

    variants_ = [(t, g, o), (_rev_bits(o), _rev_bits(g), _rev_bits(t)), (o, g ^ 1, t), (o, g, t ^ 1), (o ^ 2, g, t),
                 (o, t, g)]
    if rng.random() < 0.5:
        stem = f"Выполнили `chmod {o}{g}{t} {fname}`. Какие права покажет `ls -l` для этого файла?"
        correct = perm(o, g, t)
        cands = [perm(*x) for x in variants_]
    else:
        stem = f"`ls -l` показывает для файла {fname} права `{perm(o, g, t)}`. Какой восьмеричный код у этих прав?"
        correct = f"{o}{g}{t}"
        cands = ["".join(map(str, x)) for x in variants_]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": cands,
        "explanation": "Каждая восьмеричная цифра — сумма r=4, w=2, x=1; цифры по порядку: владелец, группа, остальные.",
    }


# --- Алгоритмы: бинарный поиск -----------------------------------------------------------------------
@template(id="core.binary_search_steps", pool="core", topics=["algorithms"], fmt="calc", a=1.2, b=-0.5,
          title="Сложность бинарного поиска", variants=500)
def _binary_search_steps(rng: random.Random) -> dict:
    if rng.random() < 0.3:
        n = 2 ** rng.randint(7, 20)  # ловушка для ответа ⌈log2 n⌉
    else:
        n = int(10 ** rng.uniform(2, 6.3))
    correct = n.bit_length()  # = floor(log2 n) + 1
    cands = [correct - 1, correct + 1, n // 2, int(n ** 0.5)]
    code = ("def search(a, x):\n    lo, hi = 0, len(a) - 1\n    steps = 0\n    while lo <= hi:\n        steps += 1\n"
            "        mid = (lo + hi) // 2\n        if a[mid] == x:\n            return steps\n"
            "        if a[mid] < x:\n            lo = mid + 1\n        else:\n            hi = mid - 1\n    return steps")
    return {
        "stem": f"Массив `a` отсортирован и содержит {_num(n)} элементов. Какое максимальное значение может вернуть "
                f"функция `search` (число итераций цикла в худшем случае)?",
        "code": code,
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": f"Каждая итерация оставляет не больше ⌊k/2⌋ элементов из k, поэтому итераций ⌊log2 n⌋ + 1 = {correct}.",
    }


# --- Python: ссылки и копии ---------------------------------------------------------------------------
@template(id="core.py_aliasing", pool="core", topics=["python"], fmt="output", a=1.3, b=-0.4,
          title="Ссылки и копирование списков в Python", variants=1000, verify=True)
def _py_aliasing(rng: random.Random) -> dict:
    kind = rng.randrange(4)
    p, q, r, s, t = rng.sample(range(1, 30), 5)
    if kind == 0:
        copy_expr = rng.choice(["a[:]", "list(a)", "a.copy()"])
        target = rng.choice(["a", "c"])
        code = f"a = [{p}, {q}, {r}]\nb = a\nc = {copy_expr}\nb.append({s})\nc.append({t})\nprint({target})"
        if target == "a":
            correct, cands = [p, q, r, s], [[p, q, r], [p, q, r, s, t], [p, q, r, t]]
        else:
            correct, cands = [p, q, r, t], [[p, q, r, s, t], [p, q, r, s], [p, q, r]]
        expl = "b — это тот же объект, что и a; c — новая (поверхностная) копия."
    elif kind == 1:
        rows, cols = rng.choice([(2, 2), (3, 2), (2, 3), (3, 3)])
        ri, ci = rng.randrange(rows), rng.randrange(cols)
        row = [0] * cols
        row[ci] = s
        correct = [row] * rows
        only = [[0] * cols for _ in range(rows)]
        only[ri][ci] = s
        cands = [only, [[0] * cols for _ in range(rows)], [[s] * cols for _ in range(rows)]]
        code = f"grid = [[0] * {cols}] * {rows}\ngrid[{ri}][{ci}] = {s}\nprint(grid)"
        expl = "Умножение списка копирует ссылки: все строки grid — один и тот же внутренний список."
    elif kind == 2:
        inplace = rng.random() < 0.5
        op = f"a += [{r}]" if inplace else f"a = a + [{r}]"
        code = f"a = [{p}, {q}]\nb = a\n{op}\na.append({s})\nprint(b)"
        correct = [p, q, r, s] if inplace else [p, q]
        cands = [[p, q], [p, q, r], [p, q, s]] if inplace else [[p, q, r, s], [p, q, r], [p, q, s]]
        expl = "`a += [...]` изменяет список на месте (b видит изменения), `a = a + [...]` создаёт новый объект."
    else:
        code = f"a = [[{p}, {q}], [{r}]]\nb = a.copy()\nb[0].append({s})\nb[1] = [{t}]\nprint(a)"
        correct = [[p, q, s], [r]]
        cands = [[[p, q], [r]], [[p, q, s], [t]], [[p, q], [t]]]
        expl = "copy() поверхностная: вложенные списки общие (append виден), а присваивание b[1] меняет только b."
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": expl,
    }


# --- Поиск ошибки в простом алгоритме -----------------------------------------------------------------
@template(id="core.algo_bug", pool="core", topics=["algorithms", "python"], fmt="bug", a=1.1, b=-0.3,
          title="Поиск ошибки в алгоритме", variants=120)
def _algo_bug(rng: random.Random) -> dict:
    kind = rng.randrange(6)
    fn = rng.choice(["solve", "calc", "run", "process", "helper"])
    xs = rng.choice(["xs", "nums", "values", "items"])
    if kind == 0:
        lines = [f"def {fn}({xs}, target):", f"    lo, hi = 0, len({xs}) - 1", "    while lo <= hi:",
                 "        mid = (lo + hi) // 2", f"        if {xs}[mid] == target:", "            return mid",
                 f"        if {xs}[mid] < target:", "            lo = mid", "        else:", "            hi = mid - 1",
                 "    return -1"]
        bug, others = "lo = mid", ["while lo <= hi:", "mid = (lo + hi) // 2", "hi = mid - 1", f"lo, hi = 0, len({xs}) - 1"]
        symptom = "На некоторых входах функция бинарного поиска зацикливается."
    elif kind == 1:
        neg = rng.sample(range(-40, -1), 3)
        lines = [f"def {fn}({xs}):", "    best = 0", f"    for x in {xs}:", "        if x > best:",
                 "            best = x", "    return best"]
        bug, others = "best = 0", ["if x > best:", "best = x", "return best", f"for x in {xs}:"]
        symptom = f"Функция должна вернуть максимум, но для {neg} возвращает 0 вместо {max(neg)}."
    elif kind == 2:
        vals = [4 * rng.randint(1, 5)] + rng.sample(range(1, 20), 2)
        vals.append(4 * rng.randint(2, 8) - sum(vals[1:]) % 4)  # суммы делятся на 4 — ответы без дробей
        right, wrong = sum(vals) / 4, sum(vals[1:]) / 4
        lines = [f"def {fn}({xs}):", "    total = 0", f"    for i in range(1, len({xs})):", f"        total += {xs}[i]",
                 f"    return total / len({xs})"]
        bug, others = f"for i in range(1, len({xs})):", ["total = 0", f"total += {xs}[i]", f"return total / len({xs})",
                                                          f"def {fn}({xs}):"]
        symptom = f"Функция должна вернуть среднее, но для {vals} возвращает {wrong} вместо {right}."
    elif kind == 3:
        word = rng.choice(["level", "radar", "abba", "kayak", "noon", "civic"])
        lines = [f"def {fn}(s):", "    n = len(s)", "    for i in range(n // 2):", "        if s[i] != s[n - i]:",
                 "            return False", "    return True"]
        bug, others = "if s[i] != s[n - i]:", ["for i in range(n // 2):", "n = len(s)", "return True", "return False"]
        symptom = f'Проверка палиндрома: вызов {fn}("{word}") падает с IndexError.'
    elif kind == 4:
        n = rng.randint(102, 987)
        lines = [f"def {fn}(n):", "    s = 0", "    while n > 0:", "        s += n % 10", "        n = n / 10",
                 "    return s"]
        bug, others = "n = n / 10", ["s += n % 10", "while n > 0:", "s = 0", "return s"]
        symptom = f"Сумма цифр: {fn}({n}) возвращает дробное число вместо {sum(map(int, str(n)))}."
    else:
        a, b, c = rng.sample(range(1, 10), 3)
        lines = [f"def {fn}({xs}):", "    seen = set()", "    out = []", f"    for x in {xs}:", "        if x in seen:",
                 "            out.append(x)", "        seen.add(x)", "    return out"]
        bug, others = "if x in seen:", ["seen.add(x)", "out.append(x)", "seen = set()", f"for x in {xs}:"]
        symptom = f"Удаление дубликатов с сохранением порядка: {fn}({[a, b, a, c]}) возвращает [{a}] вместо {[a, b, c]}."
    return {
        "stem": f"{symptom} В какой строке ошибка?",
        "code": "\n".join(lines),
        "code_lang": "python",
        "correct": bug,
        "distractors": rng.sample(others, len(others)),
        "explanation": {0: "lo = mid не сдвигает границу, когда lo == mid — нужно lo = mid + 1.",
                        1: "Начальное значение 0 больше любого отрицательного числа — нужно best = xs[0] или -inf.",
                        2: "range(1, ...) пропускает первый элемент — нужно range(len(xs)).",
                        3: "Парный индекс к i — n - 1 - i; s[n - 0] выходит за границы.",
                        4: "/ даёт float — для отбрасывания цифры нужно целочисленное деление n // 10.",
                        5: "Условие инвертировано: добавлять нужно, если x ещё не встречался (not in)."}[kind],
    }


# --- Git ----------------------------------------------------------------------------------------------
_GIT_CASES = [
    ("Последний коммит в ветке {br} ещё не запушен. Нужно отменить коммит, но оставить его изменения в индексе.",
     "git reset --soft HEAD~1", ["git reset --hard HEAD~1", "git revert HEAD", "git checkout HEAD~1"]),
    ("Коммит с ошибкой уже в общей ветке main, коллеги его забрали. Как безопасно отменить его изменения?",
     "git revert <sha>", ["git reset --hard <sha>~1 и git push --force", "git commit --amend", "git rebase -i <sha>~1 и удалить коммит"]),
    ("Нужно перенести один конкретный коммит из ветки {br} в release без остальных коммитов ветки.",
     "git cherry-pick <sha>", ["git merge {br}", "git rebase {br}", "git revert <sha>"]),
    ("В рабочей копии есть незакоммиченные правки в {f}. Нужно временно убрать их, переключиться на другую ветку, "
     "а потом вернуть.", "git stash, затем git stash pop", ["git reset --hard", "git clean -fd", "git commit --amend"]),
    ("Чем git fetch отличается от git pull?",
     "fetch только скачивает коммиты, pull = fetch + слияние (merge или rebase)",
     ["pull только скачивает коммиты, fetch = pull + слияние", "fetch отправляет локальные коммиты на сервер",
      "Ничем, это синонимы"]),
    ("В последний (ещё не запушенный) коммит забыли добавить файл {f}. Как исправить без нового коммита?",
     "git add {f} и git commit --amend --no-edit", ["git revert HEAD и git add {f}", "git stash и git add {f}",
                                                    "git reset --hard HEAD~1 и git add {f}"]),
    ("Ветка {br} отстала от main. Нужно подтянуть изменения main и получить линейную историю без merge-коммита.",
     "git rebase main (находясь в {br})", ["git merge main (находясь в {br})", "git cherry-pick main",
                                           "git reset --soft main"]),
    ("Что сделает команда git reset --hard HEAD~2 в ветке {br}?",
     "Сдвинет ветку на 2 коммита назад и сотрёт незакоммиченные правки",
     ["Создаст 2 коммита, отменяющие последние изменения", "Удалит 2 последних коммита только на сервере",
      "Сдвинет ветку на 2 коммита назад, сохранив правки в индексе"]),
]


@template(id="core.git_commands", pool="core", topics=["git"], fmt="concept", a=1.1, b=-0.2,
          title="Работа с Git", variants=35)
def _git_commands(rng: random.Random) -> dict:
    case, correct, distractors = rng.choice(_GIT_CASES)
    br = rng.choice(["feature/login", "feature/cart", "bugfix/timeout", "feature/search", "hotfix/null-check"])
    f = rng.choice(["README.md", "config.yaml", "utils.py", "schema.sql", "Dockerfile"])
    fill = {"br": br, "f": f}
    return {
        "stem": case.format(**fill),
        "correct": correct.format(**fill),
        "distractors": [d.format(**fill) for d in distractors],
        "explanation": "reset --soft сохраняет изменения в индексе, --hard стирает их; revert безопасен для общей истории; "
                       "cherry-pick переносит отдельный коммит; stash временно прячет правки; fetch не сливает.",
    }


# --- SQL: COUNT и NULL --------------------------------------------------------------------------------
@template(id="core.sql_count_null", pool="core", topics=["sql"], fmt="calc", a=1.3, b=0.2,
          title="NULL в агрегатах и условиях SQL", variants=1000)
def _sql_count_null(rng: random.Random) -> dict:
    pool = rng.sample(["SALE10", "WELCOME", "VIP", "BLACK5", "SPRING", "FRIEND"], 3)
    n = rng.randint(6, 8)
    while True:
        vals = [rng.choice(pool + [None, None]) for _ in range(n)]
        nonnull = [v for v in vals if v is not None]
        if 1 <= vals.count(None) <= 3 and len(set(nonnull)) >= 2 and len(set(nonnull)) < len(nonnull):
            break
    rows = "\n".join(f"-- {i:>2} | {v if v is not None else 'NULL'}" for i, v in enumerate(vals, 1))
    head = f"-- orders\n-- id | coupon\n{rows}\n"
    nn, d, nulls = len(nonnull), len(set(nonnull)), vals.count(None)
    if rng.random() < 0.5:
        code = head + "SELECT COUNT(*), COUNT(coupon), COUNT(DISTINCT coupon)\nFROM orders;"
        correct = f"{n}, {nn}, {d}"
        cands = [f"{n}, {n}, {d}", f"{n}, {nn}, {d + 1}", f"{nn}, {nn}, {d}", f"{n}, {n}, {d + 1}"]
        stem = "Что вернёт запрос? (значения через запятую в порядке столбцов)"
        expl = "COUNT(*) считает все строки, COUNT(col) и COUNT(DISTINCT col) пропускают NULL."
    else:
        x = rng.choice(sorted(set(nonnull)))
        code = head + f"SELECT COUNT(*)\nFROM orders\nWHERE coupon <> '{x}';"
        correct_n = sum(1 for v in nonnull if v != x)
        correct = str(correct_n)
        cands = [str(correct_n + nulls), str(vals.count(x)), str(n), str(correct_n + 1), str(correct_n - 1)]
        stem = "Сколько строк насчитает запрос?"
        expl = "Сравнение NULL <> 'X' даёт NULL (не TRUE), поэтому строки с NULL не попадают в результат."
    return {"stem": stem, "code": code, "code_lang": "sql", "correct": correct, "distractors": cands,
            "explanation": expl}


# --- Паттерны проектирования ---------------------------------------------------------------------------
_P = {"strategy": "Стратегия (Strategy)", "observer": "Наблюдатель (Observer)", "decorator": "Декоратор (Decorator)",
      "adapter": "Адаптер (Adapter)", "factory": "Фабричный метод (Factory Method)", "builder": "Строитель (Builder)",
      "facade": "Фасад (Facade)", "command": "Команда (Command)", "proxy": "Заместитель (Proxy)",
      "state": "Состояние (State)", "template": "Шаблонный метод (Template Method)", "mediator": "Посредник (Mediator)",
      "singleton": "Одиночка (Singleton)"}
_PATTERN_CASES = [
    ("Сервис расчёта {thing} должен во время выполнения выбирать один из взаимозаменяемых алгоритмов ({opts}), "
     "не меняя свой код.", "strategy", ["state", "template", "facade"]),
    ("При изменении статуса {thing} нужно оповещать произвольный набор подписчиков (почта, аналитика, кэш), "
     "не связывая их с классом напрямую.", "observer", ["mediator", "command", "decorator"]),
    ("К клиенту отправки {thing} нужно динамически добавлять логирование и повторные попытки, оборачивая объект "
     "с тем же интерфейсом.", "decorator", ["adapter", "proxy", "builder"]),
    ("Внешняя библиотека {thing} имеет метод pay(amount_cents), а наш код ожидает charge(amount). Нужно "
     "подключить её, не меняя ни библиотеку, ни наш код.", "adapter", ["facade", "decorator", "proxy"]),
    ("Создание объектов-экспортёров {thing} ({opts}) по типу нужно вынести из клиентского кода, чтобы "
     "подклассы решали, какой объект создать.", "factory", ["builder", "strategy", "singleton"]),
    ("Объект запроса {thing} имеет больше десяти необязательных параметров; нужно собирать его пошагово "
     "вместо огромного конструктора.", "builder", ["factory", "facade", "decorator"]),
    ("Для подсистем склада, оплаты и доставки {thing} нужно дать клиентам один простой метод place_order().",
     "facade", ["adapter", "mediator", "proxy"]),
    ("Действия пользователя над {thing} нужно сохранять как объекты, чтобы поддержать отмену, повтор и очередь.",
     "command", ["strategy", "observer", "state"]),
]


@template(id="core.design_patterns", pool="core", topics=["design_patterns", "oop"], fmt="concept", a=1.0, b=0.3,
          title="Паттерны проектирования", variants=100)
def _design_patterns(rng: random.Random) -> dict:
    case, correct, distractors = rng.choice(_PATTERN_CASES)
    thing = rng.choice(["заказов", "платежей", "отчётов", "уведомлений", "доставки"])
    opts = ", ".join(rng.sample(["CSV", "JSON", "XML", "PDF", "XLSX"], 3)) if correct == "factory" else \
        ", ".join(rng.sample(["по весу", "по расстоянию", "фиксированный", "по зонам", "экспресс"], 3))
    return {
        "stem": case.format(thing=thing, opts=opts) + " Какой паттерн подходит лучше всего?",
        "correct": _P[correct],
        "distractors": [_P[d] for d in distractors],
        "explanation": "Strategy — взаимозаменяемые алгоритмы; Observer — подписка на события; Decorator — обёртка "
                       "с тем же интерфейсом; Adapter — согласование интерфейсов; Factory Method — делегирование "
                       "создания; Builder — пошаговая сборка; Facade — простой вход в подсистему; Command — действие как объект.",
    }


# --- Сети: подсети CIDR -------------------------------------------------------------------------------
@template(id="core.cidr", pool="core", topics=["networking"], fmt="calc", a=1.2, b=0.5,
          title="Адресация IPv4 и маски подсети", variants=2000)
def _cidr(rng: random.Random) -> dict:
    kind = rng.randrange(3)
    if kind == 0:
        p = rng.randint(20, 29)
        net = ipaddress.ip_network(f"10.{rng.randint(0, 255)}.{rng.randint(0, 255)}.0/{p}", strict=False)
        h = 32 - p
        correct = 2 ** h - 2
        cands = [2 ** h, 2 ** h - 1, 2 ** (h - 1) - 2, 2 ** (h + 1) - 2]
        return {"stem": f"Сколько адресов можно назначить узлам (хостам) в подсети {net}?",
                "correct": str(correct), "distractors": [str(c) for c in cands],
                "explanation": f"2^(32−{p}) = {2 ** h} адресов, минус адрес сети и широковещательный."}
    p = rng.randint(21, 29)
    first = "192.168" if kind == 1 else "172.16"
    host = ipaddress.ip_address(f"{first}.{rng.randint(0, 255)}.{rng.randint(1, 254)}")
    net = ipaddress.ip_network(f"{host}/{p}", strict=False)
    wider = ipaddress.ip_network(f"{host}/{p - 1}", strict=False)
    narrower = ipaddress.ip_network(f"{host}/{p + 1}", strict=False)
    if kind == 1:
        correct = net.broadcast_address
        cands = [net.network_address, correct - 1, correct + 1, wider.broadcast_address, narrower.broadcast_address]
        stem = f"Какой широковещательный (broadcast) адрес у подсети, в которую входит узел {host}/{p}?"
        expl = f"Сеть {net}: обнуляем последние {32 - p} бит адреса узла и выставляем их в 1."
    else:
        correct = net.network_address
        zeroed = ipaddress.ip_address(f"{'.'.join(str(host).split('.')[:3])}.0")
        cands = [zeroed, correct + 1, net.broadcast_address, wider.network_address, narrower.network_address,
                 net.broadcast_address - 1]
        stem = f"Какой адрес сети у узла {host}/{p}?"
        expl = f"Адрес сети — адрес узла с обнулёнными последними {32 - p} битами: {net}."
    return {"stem": stem, "correct": str(correct), "distractors": [str(c) for c in cands], "explanation": expl}


# --- Python: изменяемые значения по умолчанию ----------------------------------------------------------
@template(id="core.py_mutable_default", pool="core", topics=["python"], fmt="output", a=1.4, b=0.6,
          title="Изменяемые аргументы по умолчанию", variants=1000, verify=True)
def _py_mutable_default(rng: random.Random) -> dict:
    fn = rng.choice(["add", "push", "collect", "remember"])
    arg = rng.choice(["bucket", "acc", "items", "store"])
    kind = rng.random()
    if kind < 0.3:
        keys = rng.sample(["a", "b", "c", "d"], 3)
        seq = [keys[0], keys[1], rng.choice(keys[:2]), keys[2]]  # хотя бы один ключ повторяется
        rng.shuffle(seq)
        seen, res = set(), []
        for k in seq:
            res.append(k in seen)
            seen.add(k)
        calls = ", ".join(f'{fn}("{k}")' for k in seq)
        code = (f"def {fn}(key, cache={{}}):\n    if key in cache:\n        return True\n    cache[key] = 1\n"
                f"    return False\n\nprint({calls})")
        correct = " ".join(map(str, res))
        cands = [" ".join(["False"] * len(seq)), " ".join(map(str, [not r for r in res])),
                 " ".join(["False"] * (len(seq) - 1) + ["True"]), " ".join(["True"] * len(seq))]
        expl = "Словарь по умолчанию создаётся один раз при определении функции и общий для всех вызовов."
        return {"stem": "Что выведет этот код?", "code": code, "code_lang": "python", "correct": correct,
                "distractors": cands, "explanation": expl}
    vals = rng.sample(range(1, 50), 4)
    n_calls = rng.choice([3, 4])
    vals = vals[:n_calls]
    while True:
        explicit = [rng.random() < 0.4 for _ in range(n_calls - 1)] + [False]
        if any(explicit) and explicit.count(False) >= 2:
            break
    lines = []
    for i, (v, ex) in enumerate(zip(vals, explicit)):
        call = f"{fn}({v}, [])" if ex else f"{fn}({v})"
        lines.append(f"r = {call}" if i == n_calls - 1 else call)
    defaults = [v for v, ex in zip(vals, explicit) if not ex]
    if kind < 0.75:
        head = f"def {fn}(x, {arg}=[]):\n    {arg}.append(x)\n    return {arg}\n\n"
        correct, cands = defaults, [[vals[-1]], vals, list(reversed(defaults))]
        expl = "Список по умолчанию создаётся один раз; его копят все вызовы без явного аргумента."
    else:
        head = (f"def {fn}(x, {arg}=None):\n    if {arg} is None:\n        {arg} = []\n    {arg}.append(x)\n"
                f"    return {arg}\n\n")
        correct, cands = [vals[-1]], [defaults, vals, []]
        expl = "При значении None новый список создаётся при каждом вызове, накопления нет."
    code = head + "\n".join(lines) + "\nprint(r)"
    return {"stem": "Что выведет этот код?", "code": code, "code_lang": "python", "correct": str(correct),
            "distractors": [str(c) for c in cands], "explanation": expl}


# --- JavaScript: var/let и event loop -----------------------------------------------------------------
@template(id="core.js_var_timeout", pool="core", topics=["javascript"], fmt="output", a=1.3, b=0.8,
          title="Замыкания и event loop в JavaScript", variants=500)
def _js_var_timeout(rng: random.Random) -> dict:
    kw = "var" if rng.random() < 0.65 else "let"
    s = rng.choice([1, 1, 2, 3])
    a = rng.randint(0, 3)
    cnt = rng.randint(2, 4)
    b = a + s * (cnt - 1) + rng.randint(1, s)  # ровно cnt итераций
    k = rng.choice([1, 2, 3, 10])
    word = rng.choice(["done", "end", "sync", "after"])
    inc = "i++" if s == 1 else f"i += {s}"
    expr = "i" if k == 1 else f"i * {k}"
    code = (f"for ({kw} i = {a}; i < {b}; {inc}) {{\n  setTimeout(() => console.log({expr}), 0);\n}}\n"
            f'console.log("{word}");')
    own = [(a + s * j) * k for j in range(cnt)]
    final = (a + s * cnt) * k
    last = (a + s * (cnt - 1)) * k
    var_out = [final] * cnt
    seq = own if kw == "let" else var_out

    def line(xs: list[int], first: bool) -> str:
        parts = [str(x) for x in xs]
        return " ".join([word, *parts] if first else [*parts, word])

    correct = line(seq, True)
    other = var_out if kw == "let" else own
    cands = [line(other, True), line(seq, False), line(other, False), line([last] * cnt, True)]
    return {
        "stem": "Что выведет код в консоль? (значения через пробел в порядке вывода)",
        "code": code,
        "code_lang": "javascript",
        "correct": correct,
        "distractors": cands,
        "explanation": "Колбэки setTimeout выполняются после синхронного кода. С var переменная одна на весь цикл "
                       "(к моменту вызова уже финальная), с let у каждой итерации своя привязка.",
    }


# --- Python: генераторы ------------------------------------------------------------------------------
@template(id="core.py_generators", pool="core", topics=["python"], fmt="output", a=1.4, b=1.1,
          title="Ленивость и исчерпание генераторов", variants=1000, verify=True)
def _py_generators(rng: random.Random) -> dict:
    kind = rng.randrange(4)
    xs = rng.sample(range(1, 20), 5)
    if kind == 0:
        k = rng.randint(2, 5)
        nums = xs[:4]
        total = sum(x * k for x in nums)
        code = f"nums = {nums}\ngen = (x * {k} for x in nums)\nprint(sum(gen), sum(gen))"
        correct, cands = f"{total} 0", [f"{total} {total}", "0 0", f"{total} {2 * total}", f"{sum(nums)} 0"]
        expl = "Генератор одноразовый: первый sum() исчерпывает его, второй получает пустую последовательность."
    elif kind == 1:
        if rng.random() < 0.75:
            t = rng.randint(1, 3)
            target = xs[t]
            correct = f"True {xs[t + 1:]}"
            cands = [f"True {xs}", "True []", f"True {xs[t:]}", f"True {[x for x in xs if x != target]}"]
            expl = "Оператор in потребляет генератор до первого совпадения включительно."
        else:
            target = rng.randint(21, 40)
            correct = "False []"
            cands = [f"False {xs}", "True []", f"False {xs[-1:]}"]
            expl = "Не найдя элемент, in исчерпывает генератор полностью — list() получает пустой список."
        code = f"gen = (x for x in {xs})\nprint({target} in gen, list(gen))"
    else:
        k = rng.choice([2, 10, 100])
        data, extra = xs[:3], xs[3:]
        if kind == 2:
            op = rng.choice([f"data.append({extra[0]})", f"data += [{extra[0]}]"])
            correct = [x * k for x in data + extra[:1]]
            cands = [[x * k for x in data], [], [x * k for x in extra[:1]]]
            expl = "Генератор ленивый и итерирует тот же объект списка, поэтому видит изменение на месте."
        else:
            op = f"data = {extra}"
            correct = [x * k for x in data]
            cands = [[x * k for x in extra], [], [x * k for x in data + extra]]
            expl = "Внешний итерируемый объект генераторного выражения вычисляется сразу: генератор держит старый список."
        code = f"data = {data}\ngen = (x * {k} for x in data)\n{op}\nprint(list(gen))"
        correct, cands = str(correct), [str(c) for c in cands]
    return {"stem": "Что выведет этот код?", "code": code, "code_lang": "python", "correct": str(correct),
            "distractors": cands, "explanation": expl}


# --- Python: замыкания и позднее связывание ---------------------------------------------------------
@template(id="core.py_late_binding", pool="core", topics=["python"], fmt="output", a=1.5, b=1.4,
          title="Замыкания и позднее связывание", variants=400, verify=True)
def _py_late_binding(rng: random.Random) -> dict:
    kind = rng.random()
    k = rng.randint(2, 6)
    n = rng.randint(3, 4)
    if kind < 0.45:
        code = f"funcs = [lambda: i * {k} for i in range({n})]\nprint([f() for f in funcs])"
        correct = [(n - 1) * k] * n
        cands = [[i * k for i in range(n)], [n * k] * n, [0] * n]
        expl = "Лямбды захватывают переменную i, а не значение; к моменту вызова i = n - 1."
    elif kind < 0.6:
        code = f"funcs = [lambda i=i: i * {k} for i in range({n})]\nprint([f() for f in funcs])"
        correct = [i * k for i in range(n)]
        cands = [[(n - 1) * k] * n, [n * k] * n, [(i + 1) * k for i in range(n)]]
        expl = "Значение по умолчанию i=i вычисляется при создании каждой лямбды и фиксирует текущее i."
    elif kind < 0.85:
        words = rng.sample(["red", "green", "blue", "cat", "dog", "sun", "sky"], 3)
        code = (f"handlers = []\nfor name in {words}:\n    def h():\n        return name.upper()\n"
                f"    handlers.append(h)\nprint([h() for h in handlers])")
        correct = [words[-1].upper()] * 3
        cands = [[w.upper() for w in words], [words[0].upper()] * 3, [words[-1]] * 3]
        expl = "Все функции h читают одну и ту же переменную name, которая после цикла указывает на последний элемент."
    else:
        a, b = rng.sample(range(2, 10), 2)
        code = (f"def make():\n    x = {a}\n    def get():\n        return x * {k}\n    x = {b}\n    return get\n\n"
                f"print(make()())")
        correct = b * k
        cands = [a * k, b, a, (a + b) * k]
        expl = "Замыкание читает значение переменной x на момент вызова get, а не на момент определения."
    return {"stem": "Что выведет этот код?", "code": code, "code_lang": "python", "correct": str(correct),
            "distractors": [str(c) for c in cands], "explanation": expl}


# --- Python/ООП: MRO и super() -----------------------------------------------------------------------
@template(id="core.py_mro", pool="core", topics=["python", "oop"], fmt="output", a=1.4, b=1.7,
          title="Множественное наследование и MRO", variants=800, verify=True)
def _py_mro(rng: random.Random) -> dict:
    base, x, y, d = rng.sample(list("ABCDEFGHKMNPRST"), 4)
    meth = rng.choice(["who", "name", "tag", "trace"])
    calls = {x: True, y: rng.random() < 0.7, d: True}
    post = {c: rng.random() < 0.35 for c in (x, y, d)}
    bases_order = (x, y) if rng.random() < 0.5 else (y, x)

    def body(c: str) -> str:
        if not calls[c]:
            return f'"{c}"'
        return f'super().{meth}() + "{c}"' if post[c] else f'"{c}" + super().{meth}()'

    code = (f"class {base}:\n    def {meth}(self):\n        return \"{base}\"\n"
            f"class {x}({base}):\n    def {meth}(self):\n        return {body(x)}\n"
            f"class {y}({base}):\n    def {meth}(self):\n        return {body(y)}\n"
            f"class {d}({bases_order[0]}, {bases_order[1]}):\n    def {meth}(self):\n        return {body(d)}\n"
            f"print({d}().{meth}())")

    def run(chain: list[str], ignore_post: bool = False, force_calls: bool = False) -> str:
        c = chain[0]
        if c == base or len(chain) == 1:
            return c
        if not (calls[c] or force_calls):
            return c
        rest = run(chain[1:], ignore_post, force_calls)
        return rest + c if post[c] and not ignore_post else c + rest

    p, q = bases_order
    correct = run([d, p, q, base])
    cands = [run([d, p, base]), run([d, q, p, base]), run([d, p, q, base], ignore_post=True),
             run([d, p, q, base], force_calls=True), run([d, q, base]), correct[::-1]]
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": correct,
        "distractors": cands,
        "explanation": f"MRO класса {d}: {d} → {p} → {q} → {base}. super() в {p} передаёт вызов следующему классу "
                       f"в MRO ({q}), а не родителю {base}; класс без super() обрывает цепочку.",
    }


# --- SQL: NOT IN / NOT EXISTS и NULL ------------------------------------------------------------------
def _sql_list(vals: list) -> str:
    return ", ".join("NULL" if v is None else str(v) for v in vals)


@template(id="core.sql_not_in_null", pool="core", topics=["sql"], fmt="calc", a=1.3, b=2.0,
          title="Трёхзначная логика SQL: NOT IN и NULL", variants=2000)
def _sql_not_in_null(rng: random.Random) -> dict:
    kind = rng.choices(["not_in", "not_in_filtered", "not_exists", "not_in_outer_null", "in"],
                       weights=[26, 16, 22, 18, 18])[0]
    ids = sorted(rng.sample(range(1, 30), rng.randint(5, 7)))
    black = rng.sample(ids, rng.randint(2, 3))
    if rng.random() < 0.5:
        black.append(rng.choice([i for i in range(1, 30) if i not in ids]))
    rng.shuffle(black)
    orders = list(ids)
    if kind == "not_in_outer_null" or (kind == "not_exists" and rng.random() < 0.5) or (kind == "in" and rng.random() < 0.5):
        orders.insert(rng.randint(0, len(orders)), None)
    if kind != "not_in_outer_null":
        black.insert(rng.randint(0, len(black)), None)
    sub_vals = {v for v in black if v is not None}
    has_null_sub = None in black

    def not_in(v, filtered: bool) -> bool:
        if v is None:
            return False
        if v in sub_vals:
            return False
        return filtered or not has_null_sub

    if kind in ("not_in", "not_in_filtered", "not_in_outer_null"):
        filt = kind == "not_in_filtered"
        sub = "SELECT b.customer_id FROM blacklist b" + (" WHERE b.customer_id IS NOT NULL" if filt else "")
        where = f"WHERE o.customer_id NOT IN (\n  {sub}\n);"
        correct = sum(not_in(v, filt) for v in orders)
    elif kind == "not_exists":
        where = "WHERE NOT EXISTS (\n  SELECT 1 FROM blacklist b\n  WHERE b.customer_id = o.customer_id\n);"
        correct = sum(v is None or v not in sub_vals for v in orders)
    else:
        where = "WHERE o.customer_id IN (SELECT b.customer_id FROM blacklist b);"
        correct = sum(v is not None and v in sub_vals for v in orders)
    naive_not_in = sum(v not in black for v in orders)          # NULL трактуется как обычное значение
    nonnull_not_in = sum(v is not None and v not in sub_vals for v in orders)
    if kind == "in":
        cands = [sum(v in black for v in orders), len(black), correct + 1, correct - 1, len(orders)]
    else:
        cands = [naive_not_in, nonnull_not_in, nonnull_not_in + 1, len(orders), 0, correct + 1, correct - 1]
    code = (f"-- orders.customer_id:    {_sql_list(orders)}\n-- blacklist.customer_id: {_sql_list(black)}\n"
            f"SELECT COUNT(*)\nFROM orders o\n{where}")
    return {
        "stem": "Что вернёт запрос (стандартная семантика SQL, например PostgreSQL)?",
        "code": code,
        "code_lang": "sql",
        "correct": str(correct),
        "distractors": [str(c) for c in cands if c >= 0],
        "explanation": "x NOT IN (…, NULL) никогда не даёт TRUE: сравнение с NULL — UNKNOWN; NULL NOT IN (…) тоже "
                       "UNKNOWN. NOT EXISTS не страдает от NULL: строка без пары считается. IN находит только совпадения.",
    }
