"""Пул шаблонов специализации «frontend». Каждый шаблон регистрируется декоратором @template (см. base.py).

Ответы JavaScript/TypeScript/React-шаблонов вычисляются в генераторах явной логикой и сверены прогоном
сгенерированного кода (node, tsc --strict, React 18 + jsdom) на зёрнах 0..49.
"""
import itertools
import random
from collections import deque

from app.services.bank.base import template

_LETTERS = list("ABCDEFGHKLMNPRSTXZ")


def _swaps(seq: list, rng: random.Random, n: int = 8) -> list[list]:
    """Перестановки соседних элементов верного порядка — запасные правдоподобные дистракторы."""
    out = []
    for _ in range(n):
        s = list(seq)
        i = rng.randrange(len(s) - 1)
        s[i], s[i + 1] = s[i + 1], s[i]
        out.append(s)
    return out


def _flips(correct: list[str], naive: list[str]) -> list[str]:
    """Все комбинации «верно/наивно» по позициям, кроме полностью верной (строки через пробел)."""
    pos = [i for i in range(len(correct)) if correct[i] != naive[i]]
    out = []
    for mask in range(1, 1 << len(pos)):
        cur = list(correct)
        for j, p in enumerate(pos):
            if mask >> j & 1:
                cur[p] = naive[p]
        out.append(" ".join(cur))
    out.sort(key=lambda s: -sum(1 for x, y in zip(s.split(" "), naive) if x == y))
    return out


# ---------------------------------------------------------------------------------------------- javascript basics

@template(id="frontend.js_coercion", pool="frontend", topics=["javascript"], fmt="output", a=1.2, b=-1.4,
          title="Приведение типов в JavaScript", variants=500)
def _js_coercion(rng: random.Random) -> dict:
    x, y = rng.choice([("a", "b"), ("x", "y"), ("left", "right"), ("price", "qty"), ("raw", "step"), ("s", "n")])
    s, n = rng.randint(2, 9), rng.randint(2, 9)
    # (выражение, верный вывод, вывод при «числовом» понимании операторов)
    concat = [(f"{x} + {y}", f"{s}{n}", str(s + n)),
              (f"{y} + {x}", f"{n}{s}", str(n + s)),
              (f"{y} + 1 + {x}", f"{n + 1}{s}", str(n + 1 + s))]
    numeric = [(f"{x} - {y}", str(s - n), "NaN"),
               (f"{x} * {y}", str(s * n), "NaN"),
               (f"+{x} + {y}", str(s + n), f"{s}{n}")]
    exprs = [rng.choice(concat), rng.choice(numeric)]
    rng.shuffle(exprs)
    correct = [e[1] for e in exprs]
    naive = [e[2] for e in exprs]
    quoted = " ".join(f'"{c}"' if e in concat else c for c, e in zip(correct, exprs))
    code = f'const {x} = "{s}";\nconst {y} = {n};\nconsole.log({exprs[0][0]}, {exprs[1][0]});'
    return {
        "stem": "Что выведет этот код в консоль?",
        "code": code,
        "code_lang": "javascript",
        "correct": " ".join(correct),
        "distractors": [*_flips(correct, naive), quoted],
        "explanation": "Бинарный + со строкой склеивает строки (вычисление идёт слева направо); -, * и унарный + "
                       "приводят операнды к числу.",
    }


@template(id="frontend.js_array_chain", pool="frontend", topics=["javascript"], fmt="output", a=1.2, b=-0.8,
          title="Методы массивов filter / map / reduce", variants=2000)
def _js_array_chain(rng: random.Random) -> dict:
    preds = {
        "even": ("(n) => n % 2 === 0", lambda v: v % 2 == 0),
        "odd": ("(n) => n % 2 !== 0", lambda v: v % 2 != 0),
    }
    while True:
        nums = rng.sample(range(1, 21), 6)
        kind = rng.choice(["even", "odd", "gt", "lt"])
        t = rng.randint(7, 14)
        if kind == "gt":
            ptxt, p = f"(n) => n > {t}", (lambda v, t=t: v > t)
        elif kind == "lt":
            ptxt, p = f"(n) => n < {t}", (lambda v, t=t: v < t)
        else:
            ptxt, p = preds[kind]
        k = rng.randint(2, 4)
        if rng.random() < 0.5:
            mtxt, f = f"(n) => n * {k}", (lambda v, k=k: v * k)
        else:
            mtxt, f = f"(n) => n + {k}", (lambda v, k=k: v + k)
        init = rng.randint(1, 10)
        kept = [v for v in nums if p(v)]
        if not 2 <= len(kept) <= 4:
            continue
        correct = sum(f(v) for v in kept) + init
        cands = [sum(f(v) for v in nums) + init,  # фильтр проигнорирован
                 sum(f(v) for v in kept),  # потеряно начальное значение
                 sum(f(v) for v in nums if not p(v)) + init,  # условие фильтра понято наоборот
                 sum(kept) + init,  # map не применён
                 sum(f(v) for v in kept) + f(init)]
        if len({c for c in cands if c != correct}) >= 3:
            break
    arr = rng.choice(["nums", "values", "scores", "items"])
    code = (f"const {arr} = [{', '.join(map(str, nums))}];\n"
            f"const total = {arr}\n"
            f"  .filter({ptxt})\n"
            f"  .map({mtxt})\n"
            f"  .reduce((acc, n) => acc + n, {init});\n"
            f"console.log(total);")
    return {
        "stem": "Что выведет этот код в консоль?",
        "code": code,
        "code_lang": "javascript",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": f"filter оставляет {kept}, map преобразует каждый элемент, reduce суммирует, начиная с {init}.",
    }


@template(id="frontend.js_closure_loop", pool="frontend", topics=["javascript"], fmt="output", a=1.4, b=-0.2,
          title="Замыкания в цикле: var и let", variants=600)
def _js_closure_loop(rng: random.Random) -> dict:
    decl = rng.choice(["var", "let"])
    arr = rng.choice(["fns", "handlers", "callbacks", "tasks"])
    v = rng.choice(["i", "j", "k"])
    start = rng.randint(0, 2)
    step = rng.choice([1, 1, 2])
    count = rng.choice([3, 3, 4])
    if rng.random() < 0.5:
        op, bound = "<", start + step * count
    else:
        op, bound = "<=", start + step * (count - 1)
    it = [start + step * j for j in range(count)]
    final = start + step * count
    if rng.random() < 0.5:
        m = rng.randint(2, 10)
        body, f = f"{v} * {m}", (lambda q: q * m)
    else:
        m = rng.randint(1, 9)
        body, f = f"{v} + {m}", (lambda q: q + m)
    upd = f"{v}++" if step == 1 else f"{v} += {step}"
    let_res = [f(q) for q in it]
    var_res = [f(final)] * count
    last_res = [f(it[-1])] * count
    shifted = [f(q + step) for q in it]
    correct, other = (var_res, let_res) if decl == "var" else (let_res, var_res)
    code = (f"const {arr} = [];\n"
            f"for ({decl} {v} = {start}; {v} {op} {bound}; {upd}) {{\n"
            f"  {arr}.push(() => {body});\n"
            f"}}\n"
            f"console.log({arr}.map((f) => f()).join(\",\"));")

    def j(xs):
        return ",".join(map(str, xs))

    return {
        "stem": "Что выведет этот код в консоль?",
        "code": code,
        "code_lang": "javascript",
        "correct": j(correct),
        "distractors": [j(other), j(last_res), j(shifted), j([f(start)] * count)],
        "explanation": "С var переменная цикла одна на все итерации, и к моменту вызова функций она уже равна "
                       f"{final}. С let каждая итерация получает собственную привязку.",
    }


@template(id="frontend.js_this_binding", pool="frontend", topics=["javascript"], fmt="output", a=1.4, b=0.8,
          title="Привязка this: call, bind, стрелочные функции", variants=2000)
def _js_this_binding(rng: random.Random) -> dict:
    a, b = rng.choice([("alpha", "beta"), ("cat", "dog"), ("left", "right"), ("first", "second"), ("src", "dst")])
    prop = rng.choice(["v", "id", "size", "n"])
    va, vb = rng.sample(range(1, 10), 2)
    # (выражение, верный источник this, «наивный» ответ)
    pool = [
        (f"{b}.get()", "B", "A"),
        (f"{a}.get.call({b})", "B", "A"),
        (f"{a}.get.bind({b}).call({a})", "B", "A"),
        (f"{a}.get.bind({a}).bind({b})()", "A", "B"),
        (f"{a}.wrap()()", "A", "U"),
        (f"{a}.wrap().call({b})", "A", "B"),
        (f"{a}.wrap.call({b})()", "B", "A"),
        (f"{b}.get.call({a})", "A", "B"),
    ]
    exprs = rng.sample(pool, 3)
    val = {"A": str(va), "B": str(vb), "U": "undefined"}
    correct = [val[e[1]] for e in exprs]
    naive = [val[e[2]] for e in exprs]
    code = (f"const {a} = {{\n"
            f"  {prop}: {va},\n"
            f"  get() {{ return this.{prop}; }},\n"
            f"  wrap() {{ return () => this.{prop}; }},\n"
            f"}};\n"
            f"const {b} = {{ {prop}: {vb}, get: {a}.get }};\n"
            f"console.log(\n"
            f"  {exprs[0][0]},\n"
            f"  {exprs[1][0]},\n"
            f"  {exprs[2][0]}\n"
            f");")
    return {
        "stem": "Что выведет этот код в консоль?",
        "code": code,
        "code_lang": "javascript",
        "correct": " ".join(correct),
        "distractors": _flips(correct, naive),
        "explanation": "this обычной функции определяется способом вызова (obj.f(), call); bind фиксирует this "
                       "навсегда — повторный bind и call его не меняют; стрелочная функция берёт this из места "
                       "создания и игнорирует call.",
    }


# ---------------------------------------------------------------------------------------------- event loop

def _el_simulate(nodes: list, mode: str = "ok") -> list[str]:
    """Модель event loop. mode — правильная модель или типичное заблуждение для дистрактора."""
    out: list[str] = []
    micro: deque = deque()
    macro: deque = deque()

    def run(body: list) -> None:
        for node in body:
            k = node[0]
            if k == "log":
                out.append(node[1])
            elif k == "timeout":
                macro.append(node[1])
            elif k in ("then", "micro"):
                micro.append(node[1])
            elif k == "chain":
                if mode == "chain_flat":
                    micro.append([("log", node[1]), ("log", node[2])])
                else:
                    micro.append([("log", node[1]), ("then", [("log", node[2])])])
            elif k == "ctor":
                if mode == "ctor_async":
                    micro.append([("log", node[1]), ("log", node[2])])
                else:
                    out.append(node[1])
                    micro.append([("log", node[2])])
            elif k == "async":
                out.append(node[1])
                if mode == "await_sync":
                    out.append(node[2])
                else:
                    micro.append([("log", node[2])])

    run(nodes)
    while micro or macro:
        if mode == "macro_first":
            run(macro.popleft() if macro else micro.popleft())
        elif mode == "batch_timers" and macro:
            while micro:
                run(micro.popleft())
            batch = list(macro)
            macro.clear()
            for m in batch:
                run(m)
        else:
            if micro:
                run(micro.popleft())
            else:
                run(macro.popleft())
    return out


def _el_source_order(nodes: list) -> list[str]:
    out = []
    for node in nodes:
        if node[0] == "log":
            out.append(node[1])
        elif node[0] in ("timeout", "then", "micro"):
            out += _el_source_order(node[1])
        else:
            out += [node[1], node[2]]
    return out


def _el_render(node: tuple, ind: str = "") -> list[str]:
    k = node[0]
    if k == "log":
        return [f'{ind}console.log("{node[1]}");']
    if k == "chain":
        return [f'{ind}Promise.resolve().then(() => console.log("{node[1]}")).then(() => console.log("{node[2]}"));']
    if k == "ctor":
        return [f'{ind}new Promise((res) => {{ console.log("{node[1]}"); res(); }}).then(() => console.log("{node[2]}"));']
    if k == "async":
        return [f'{ind}(async () => {{ console.log("{node[1]}"); await null; console.log("{node[2]}"); }})();']
    body = node[1]
    head, tail = {"timeout": ("setTimeout(() => ", ", 0);"), "then": ("Promise.resolve().then(() => ", ");"),
                  "micro": ("queueMicrotask(() => ", ");")}[k]
    if len(body) == 1 and body[0][0] == "log":
        return [f'{ind}{head}console.log("{body[0][1]}"){tail}']
    lines = [f"{ind}{head}{{"]
    for b in body:
        lines += _el_render(b, ind + "  ")
    lines.append(f"{ind}}}{tail}")
    return lines


def _el_item(rng: random.Random, nodes: list) -> dict:
    correct = _el_simulate(nodes)
    cands = [_el_source_order(nodes)]
    for mode in ("macro_first", "batch_timers", "chain_flat", "ctor_async", "await_sync"):
        cands.append(_el_simulate(nodes, mode))
    rng.shuffle(cands)
    cands += _swaps(correct, rng)
    code = "\n".join(line for n in nodes for line in _el_render(n))
    return {
        "stem": "В каком порядке будут выведены сообщения? (Ответ — сообщения через пробел в порядке вывода.)",
        "code": code,
        "code_lang": "javascript",
        "correct": " ".join(correct),
        "distractors": [" ".join(c) for c in cands if c != correct],
        "explanation": "Сначала выполняется весь синхронный код (включая тело executor у new Promise и код async-"
                       "функции до первого await), затем очередь микрозадач целиком (then, queueMicrotask, "
                       "продолжения после await; новые микрозадачи добавляются в конец той же очереди), и только "
                       "потом по одной макрозадаче (setTimeout) — после каждой снова опустошаются микрозадачи.",
    }


@template(id="frontend.event_loop_basic", pool="frontend", topics=["javascript", "browser"], fmt="output",
          a=1.4, b=0.3, title="Порядок выполнения в event loop", variants=3000)
def _event_loop_basic(rng: random.Random) -> dict:
    while True:
        labels = rng.sample(_LETTERS, 6)
        n_sync = rng.choice([2, 3])
        n_to = rng.choice([1, 2])
        n_mi = 6 - n_sync - n_to
        kinds = ["log"] * n_sync + ["timeout"] * n_to + [rng.choice(["then", "then", "micro"]) for _ in range(n_mi)]
        rng.shuffle(kinds)
        nodes = [("log", lab) if k == "log" else (k, [("log", lab)]) for k, lab in zip(kinds, labels)]
        correct = _el_simulate(nodes)
        if correct != _el_source_order(nodes) and kinds[0] != "log":
            return _el_item(rng, nodes)


@template(id="frontend.event_loop_advanced", pool="frontend", topics=["javascript", "browser", "concurrency"],
          fmt="output", a=1.5, b=2.0, title="Event loop: вложенные задачи, цепочки then, async/await",
          variants=5000)
def _event_loop_advanced(rng: random.Random) -> dict:
    while True:
        labels = iter(rng.sample(_LETTERS, len(_LETTERS)))
        adv = rng.sample(["chain", "ctor", "async", "to_nested", "then_nested", "then_nested2"], 3)
        kinds = adv + ["log", rng.choice(["log", "timeout", "micro"])]
        rng.shuffle(kinds)
        nodes = []
        for k in kinds:
            if k == "log":
                nodes.append(("log", next(labels)))
            elif k in ("timeout", "micro"):
                nodes.append((k, [("log", next(labels))]))
            elif k in ("chain", "ctor", "async"):
                nodes.append((k, next(labels), next(labels)))
            elif k == "to_nested":
                inner = rng.choice(["then", "micro"])
                nodes.append(("timeout", [("log", next(labels)), (inner, [("log", next(labels))])]))
            elif k == "then_nested":
                nodes.append(("then", [("timeout", [("log", next(labels))]), ("log", next(labels))]))
            else:
                nodes.append(("then", [("log", next(labels)), ("micro", [("log", next(labels))])]))
        code_lines = sum(len(_el_render(n)) for n in nodes)
        correct = _el_simulate(nodes)
        n_wrong = len({tuple(_el_simulate(nodes, m)) for m in ("macro_first", "batch_timers", "chain_flat",
                                                                "ctor_async", "await_sync")} - {tuple(correct)})
        if code_lines <= 15 and n_wrong >= 2 and kinds[0] != "log":
            return _el_item(rng, nodes)


@template(id="frontend.promise_combinators", pool="frontend", topics=["javascript", "concurrency"], fmt="output",
          a=1.3, b=0.6, title="Promise.all / race / any / allSettled", variants=1500)
def _promise_combinators(rng: random.Random) -> dict:
    def outcome(comb: str, ps: list) -> str:
        by_time = sorted(ps, key=lambda p: p[0])
        if comb == "all":
            rej = [p for p in by_time if p[2]]
            return f"fail {rej[0][1]}" if rej else "ok " + ",".join(p[1] for p in ps)
        if comb == "race":
            p = by_time[0]
            return f"{'fail' if p[2] else 'ok'} {p[1]}"
        if comb == "any":
            ok = [p for p in by_time if not p[2]]
            return f"ok {ok[0][1]}" if ok else "fail AggregateError: All promises were rejected"
        return ",".join("rejected" if p[2] else "fulfilled" for p in ps)

    while True:
        comb = rng.choice(["all", "race", "any", "allSettled"])
        vals = rng.sample(["a", "b", "c", "x", "y", "z", "p", "q"], 3)
        delays = rng.sample([10, 20, 30, 40, 50], 3)
        fails = [rng.random() < 0.45 for _ in range(3)]
        ps = list(zip(delays, vals, fails))
        if comb == "any" and all(fails):
            continue
        if comb in ("all", "allSettled") and not any(fails):
            continue
        correct = outcome(comb, ps)
        by_time = sorted(ps, key=lambda p: p[0])
        cands = [outcome(c, ps) for c in ("all", "race", "any") if c != comb]
        cands += ["ok " + ",".join(p[1] for p in by_time),
                  ",".join("rejected" if p[2] else "fulfilled" for p in by_time),
                  f"ok {ps[0][1]}", f"fail {by_time[0][1]}", f"ok {by_time[0][1]}"]
        if comb == "allSettled":
            cands = [",".join("rejected" if p[2] else "fulfilled" for p in by_time),
                     "fulfilled,fulfilled,fulfilled", f"fail {[p for p in by_time if p[2]][0][1]}",
                     "ok " + ",".join(p[1] for p in ps)]
        uniq = {c for c in cands if c != correct}
        if len(uniq) >= 3:
            break
    args = ", ".join(f'wait({d}, "{v}"{", true" if f else ""})' for d, v, f in ps)
    handler = ('  .then((rs) => console.log(rs.map((r) => r.status).join(",")));' if comb == "allSettled" else
               '  .then((v) => console.log("ok " + v))\n  .catch((e) => console.log("fail " + e));')
    code = ("const wait = (ms, value, fail = false) =>\n"
            "  new Promise((resolve, reject) =>\n"
            "    setTimeout(() => (fail ? reject(value) : resolve(value)), ms));\n\n"
            f"Promise.{comb}([{args}])\n{handler}")
    return {
        "stem": "Что выведет этот код в консоль?",
        "code": code,
        "code_lang": "javascript",
        "correct": correct,
        "distractors": list(dict.fromkeys(cands)),
        "explanation": "all — массив значений в порядке аргументов или первая ошибка по времени; race — первый "
                       "завершившийся (успех или ошибка); any — первый успешный; allSettled — статусы всех "
                       "промисов в порядке аргументов.",
    }


# ---------------------------------------------------------------------------------------------- browser / DOM

@template(id="frontend.dom_event_phases", pool="frontend", topics=["browser", "javascript"], fmt="output",
          a=1.3, b=1.2, title="Всплытие и перехват событий DOM", variants=3000)
def _dom_event_phases(rng: random.Random) -> dict:
    outer, middle, inner = rng.choice([("page", "card", "btn"), ("form", "row", "submit"), ("list", "item", "link"),
                                       ("modal", "footer", "close"), ("menu", "group", "entry")])
    while True:
        labels = iter(rng.sample(_LETTERS, len(_LETTERS)))
        regs = []  # (узел, метка, capture, stop)
        for node in (outer, middle):
            for _ in range(rng.choice([1, 2])):
                regs.append([node, next(labels), rng.random() < 0.5, False])
        regs.append([inner, next(labels), False, False])
        rng.shuffle(regs)
        if rng.random() < 0.5:
            cand = [r for r in regs if r[0] != inner]
            rng.choice(cand)[3] = True
        if not 4 <= len(regs) <= 5:
            continue

        def dispatch(ignore_capture=False, stop_ignored=False, no_stop_same_node=False):
            out = []
            path = [(outer, True), (middle, True), (inner, None), (middle, False), (outer, False)]
            for node, cap in path:
                stopped = False
                for r in regs:
                    if r[0] != node:
                        continue
                    if cap is not None:
                        phase_cap = r[2] and not ignore_capture
                        if phase_cap != cap:
                            continue
                    if no_stop_same_node and stopped:
                        break
                    out.append(r[1])
                    if r[3] and not stop_ignored:
                        stopped = True
                if stopped:
                    return out
            return out

        correct = dispatch()
        cands = [dispatch(ignore_capture=True), dispatch(stop_ignored=True),
                 dispatch(no_stop_same_node=True),
                 [r[1] for r in regs],  # в порядке регистрации
                 list(reversed(dispatch(ignore_capture=True)))]
        if any(r[2] for r in regs) and len({tuple(c) for c in cands} - {tuple(correct)}) >= 2 and len(correct) >= 2:
            break
    cands += _swaps(correct, rng)
    lines = ["const log = (s) => console.log(s);"]
    for node, lab, cap, stop in regs:
        cb = f'(e) => {{ log("{lab}"); e.stopPropagation(); }}' if stop else f'() => log("{lab}")'
        lines.append(f'{node}.addEventListener("click", {cb}{", true" if cap else ""});')
    return {
        "stem": f"Разметка: div#{outer} > div#{middle} > button#{inner}; переменные {outer}, {middle}, {inner} "
                f"ссылаются на эти элементы. Пользователь кликает по кнопке. Что появится в консоли? "
                f"(Сообщения через пробел в порядке вывода.)",
        "code": "\n".join(lines),
        "code_lang": "javascript",
        "correct": " ".join(correct),
        "distractors": [" ".join(c) for c in cands if c != correct],
        "explanation": "Сначала фаза перехвата сверху вниз (обработчики с capture = true), затем обработчики на "
                       "самой цели, затем всплытие снизу вверх. stopPropagation останавливает переход к следующим "
                       "узлам, но остальные обработчики текущего узла выполняются.",
    }


@template(id="frontend.a11y_semantics", pool="frontend", topics=["html", "a11y"], fmt="concept", a=1.0, b=-1.3,
          title="Семантическая вёрстка и доступность", variants=60)
def _a11y_semantics(rng: random.Random) -> dict:
    item = rng.choice(["товар", "заказ", "файл", "комментарий", "адрес"])
    variant = rng.randrange(7)
    if variant == 0:
        n = rng.randint(10, 99)
        return {
            "stem": f"Кнопка удаления ({item}) свёрстана так. Что исправить в первую очередь, чтобы ею могли "
                    f"пользоваться с клавиатуры и через скринридер?",
            "code": f'<div class="icon-btn" onclick="remove({n})">\n  <svg aria-hidden="true">…</svg>\n</div>',
            "code_lang": "html",
            "correct": "Заменить div на <button> и задать aria-label с названием действия",
            "distractors": ["Добавить div атрибут title с названием действия",
                            "Добавить svg атрибут alt с названием действия",
                            "Задать div стиль cursor: pointer",
                            "Увеличить иконку до 44×44 px"],
            "explanation": "div не получает фокус и не реагирует на Enter/Space; у кнопки-иконки нет текстового "
                           "имени — его даёт aria-label.",
        }
    if variant == 1:
        chart = rng.choice(["продаж по месяцам", "посещаемости за неделю", "выручки по регионам", "нагрузки на сервис"])
        name = rng.choice(["sales", "visits", "revenue", "load"])
        return {
            "stem": f"В статье есть график {chart}, без которого текст непонятен. Как правильно задать "
                    f"альтернативный текст изображения?",
            "code": f'<img src="/img/{name}-chart.png">',
            "code_lang": "html",
            "correct": "alt с кратким описанием того, что показывает график",
            "distractors": ['alt="" — скринридер всё равно не озвучит график',
                            'alt="image" или alt="график"',
                            "Атрибут title вместо alt",
                            "Ничего: скринридер прочитает имя файла"],
            "explanation": "Информативное изображение должно иметь alt, передающий его смысл.",
        }
    if variant == 2:
        deco = rng.choice(["divider", "wave", "dots", "corner"])
        return {
            "stem": "Изображение ниже — чисто декоративный элемент оформления, смысла не несёт. Как правильно "
                    "его разметить?",
            "code": f'<img src="/img/{deco}-{rng.randint(1, 9)}.svg">',
            "code_lang": "html",
            "correct": 'Указать пустой alt="" — скринридер пропустит изображение',
            "distractors": ["Не указывать alt вообще",
                            f'alt="{deco}"',
                            'role="img" и aria-label="декор"',
                            'alt="изображение"'],
            "explanation": "Пустой alt помечает изображение как декоративное; без alt скринридер может прочитать "
                           "имя файла.",
        }
    if variant == 3:
        field, fid, ftype = rng.choice([("Электронная почта", "email", "email"), ("Телефон", "phone", "tel"),
                                        ("Пароль", "password", "password"), ("Имя", "first-name", "text")])
        return {
            "stem": f"При фокусе на поле «{field}» скринридер не озвучивает его подпись. Как исправить?",
            "code": f'<span>{field}</span>\n<input type="{ftype}" id="{fid}">',
            "code_lang": "html",
            "correct": f'Заменить span на <label for="{fid}">',
            "distractors": [f'Добавить полю name="{fid}"',
                            "Перенести текст подписи в placeholder",
                            "Обернуть span и input в общий <div>",
                            f'Добавить span атрибут id="{fid}-label"'],
            "explanation": "label с for (или обёртка label вокруг input) программно связывает подпись с полем.",
        }
    if variant == 4:
        text, page = rng.choice([("Все заказы", "orders"), ("Профиль", "profile"), ("Справка", "help"),
                                 ("Корзина", "cart")])
        return {
            "stem": f"Элемент «{text}» переводит пользователя на страницу /{page}. Какой HTML-элемент выбрать?",
            "code": None,
            "correct": f'<a href="/{page}">{text}</a>',
            "distractors": [f'<button onclick="location.href=\'/{page}\'">',
                            f'<span class="link" data-href="/{page}">',
                            f'<div onclick="go(\'/{page}\')">'],
            "explanation": "Навигация — это ссылка: она доступна с клавиатуры, открывается в новой вкладке и "
                           "правильно озвучивается.",
        }
    if variant == 5:
        title = rng.choice(["Тарифы", "О компании", "Документация", "Вакансии"])
        lvl = rng.choice([4, 5])
        return {
            "stem": f"На странице после <h1>{title}</h1> заголовки разделов свёрстаны как <h{lvl}>, «потому что у "
                    f"них меньше шрифт». Что не так?",
            "code": None,
            "correct": "Нарушена иерархия: нужны <h2>, а размер задаётся через CSS",
            "distractors": ["Ничего: уровень заголовка влияет только на размер шрифта",
                            "На странице допустим только один заголовок любого уровня",
                            "Подзаголовки нужно делать через <b>, а не <h*>"],
            "explanation": "Скринридеры строят навигацию по уровням заголовков; пропуск уровней её ломает.",
        }
    sel = rng.choice(["button", ".btn", "a, button", "*"])
    return {
        "stem": "Дизайнер просит убрать «некрасивую рамку» вокруг элементов при фокусе. Как поступить правильно?",
        "code": f"{sel}:focus {{\n  outline: none;\n}}",
        "code_lang": "css",
        "correct": "Оставить видимый фокус, например стилизовать :focus-visible",
        "distractors": ["Убрать outline: фокус нужен только скринридерам",
                        "Убрать outline и добавить tabindex=\"-1\"",
                        "Убрать outline, фокус и так виден по курсору мыши"],
        "explanation": "Без видимого индикатора фокуса пользователь клавиатуры не понимает, где находится.",
    }


@template(id="frontend.http_caching", pool="frontend", topics=["http", "browser"], fmt="concept", a=1.2, b=1.0,
          title="HTTP-кэширование: Cache-Control и ETag", variants=200)
def _http_caching(rng: random.Random) -> dict:
    res = rng.choice(["/api/catalog", "/api/profile", "/static/app.css", "/data/prices.json", "/api/news"])
    etag = f'"{rng.choice("abcdef")}{rng.randint(100, 999)}"'
    variant = rng.randrange(6)
    if variant in (0, 1):
        m = rng.choice([60, 120, 300, 600, 900])
        if variant == 0:
            t = rng.randint(2, m // 30) * 15 if m >= 60 else 30
            t = min(t, m - 15)
            stem = f"Через {t} с после первой загрузки страница снова запрашивает {res}. Что произойдёт?"
            correct = "Ответ возьмётся из кэша браузера без обращения к серверу"
            dis = ["Браузер отправит запрос с If-None-Match и получит 304",
                   "Браузер отправит обычный запрос и получит 200 с телом",
                   "Браузер отправит запрос с If-Modified-Since и получит 304"]
        else:
            t = m + rng.choice([30, 60, 120, 300])
            stem = (f"Через {t} с после первой загрузки страница снова запрашивает {res}. "
                    f"Ресурс на сервере не менялся. Что произойдёт?")
            correct = f"Условный запрос с If-None-Match: {etag}, сервер ответит 304"
            dis = ["Ответ возьмётся из кэша без обращения к серверу",
                   "Браузер скачает ресурс заново с ответом 200",
                   "Браузер вернёт ошибку: кэшированная копия устарела"]
        code = f"HTTP/1.1 200 OK\nCache-Control: max-age={m}\nETag: {etag}"
    elif variant == 2:
        code = f"HTTP/1.1 200 OK\nCache-Control: no-cache\nETag: {etag}"
        stem = f"Сервер отдаёт {res} с такими заголовками. Что верно?"
        correct = "Ответ кэшируется, но перед каждым использованием проверяется на сервере"
        dis = ["Ответ вообще не сохраняется в кэше браузера",
               "Ответ кэшируется навсегда, пока не сменится ETag",
               "Ответ кэшируется только CDN, но не браузером"]
    elif variant == 3:
        code = "HTTP/1.1 200 OK\nCache-Control: no-store"
        stem = f"Ответ {res} содержит персональные данные, сервер отдаёт такой заголовок. Что верно?"
        correct = "Ответ не сохраняется ни в каком кэше, каждый раз полный запрос"
        dis = ["Ответ сохраняется, но каждый раз ревалидируется (возможен 304)",
               "Ответ кэшируется в браузере, но не в CDN",
               "Ответ кэшируется до закрытия вкладки"]
    elif variant == 4:
        m = rng.choice([60, 300, 600, 3600])
        code = f"HTTP/1.1 200 OK\nCache-Control: private, max-age={m}"
        stem = f"Между браузером и сервером стоит CDN. Ответ {res} пришёл с таким заголовком. Что верно?"
        correct = f"Браузер может хранить ответ {m} с, CDN кэшировать не должен"
        dis = [f"И браузер, и CDN могут хранить ответ {m} с",
               f"CDN хранит ответ {m} с, браузер не кэширует",
               "Никто не кэширует: private запрещает кэш"]
    else:
        h = "".join(rng.choice("0123456789abcdef") for _ in range(8))
        name = rng.choice(["app", "vendor", "main", "chunk"])
        code = f"GET /static/{name}.{h}.js\n\nHTTP/1.1 200 OK\nCache-Control: public, max-age=31536000, immutable"
        stem = "Как при такой настройке пользователи получат новую версию бандла после релиза?"
        correct = "Новый бандл будет с другим хешем в имени — это новый URL"
        dis = ["Браузер увидит изменения через If-None-Match и получит 200",
               "Только через год, когда истечёт max-age",
               "При обычной перезагрузке страницы (F5) браузер скачает файл заново"]
    return {
        "stem": stem,
        "code": code,
        "code_lang": "http",
        "correct": correct,
        "distractors": dis,
        "explanation": "max-age — срок свежести без запросов; по истечении — ревалидация по ETag (304); no-cache — "
                       "ревалидация всегда; no-store — не хранить; private — только кэш браузера; immutable + хеш "
                       "в имени — версия меняется сменой URL.",
    }


@template(id="frontend.cors_preflight", pool="frontend", topics=["http", "browser"], fmt="concept", a=1.4, b=1.4,
          title="CORS: когда отправляется preflight", variants=2000)
def _cors_preflight(rng: random.Random) -> dict:
    simple = ["GET без дополнительных заголовков",
              "POST, Content-Type: text/plain",
              "POST, Content-Type: application/x-www-form-urlencoded",
              "POST, Content-Type: multipart/form-data",
              'GET с credentials: "include" (куки)',
              "GET, Accept: application/json",
              "HEAD без дополнительных заголовков",
              "GET, Accept-Language: ru-RU"]
    pre = ["POST, Content-Type: application/json",
           "GET, Authorization: Bearer <token>",
           "PUT, Content-Type: text/plain",
           "DELETE без дополнительных заголовков",
           "PATCH, Content-Type: application/json",
           "GET, X-Request-Id: <uuid>",
           "POST, Content-Type: text/plain + X-Trace-Id",
           "PUT без тела и заголовков"]
    host = rng.choice(["shop", "crm", "portal", "lk", "admin"])
    want_pre = rng.random() < 0.5
    if want_pre:
        correct = rng.choice(pre)
        dis = rng.sample(simple, 3)
        q = "Для какого запроса браузер отправит предварительный запрос OPTIONS (preflight)?"
    else:
        correct = rng.choice(simple)
        dis = rng.sample(pre, 3)
        q = "Для какого запроса браузер НЕ отправит предварительный запрос OPTIONS (preflight)?"
    return {
        "stem": f"Скрипт со страницы https://{host}.test делает fetch на https://api.{host}.test. {q}",
        "code": None,
        "correct": correct,
        "distractors": dis,
        "explanation": "Preflight не нужен только «простым» запросам: метод GET/HEAD/POST и лишь безопасные "
                       "заголовки (Accept, Accept-Language, Content-Language, Content-Type со значениями "
                       "text/plain, multipart/form-data, application/x-www-form-urlencoded). Куки сами по себе "
                       "preflight не вызывают.",
    }


# ---------------------------------------------------------------------------------------------- css

@template(id="frontend.css_box_model", pool="frontend", topics=["css"], fmt="calc", a=1.3, b=-0.4,
          title="Блочная модель CSS и box-sizing", variants=3000)
def _css_box_model(rng: random.Random) -> dict:
    while True:
        sizing = rng.choice(["content-box", "border-box"])
        w = rng.choice(range(160, 401, 20))
        pt, pb = rng.choice([4, 6, 8, 10]), rng.choice([4, 6, 8, 10])
        pl, pr = rng.choice([12, 16, 20, 24]), rng.choice([12, 16, 20, 24])
        form = rng.choice([1, 2, 3, 4])
        if form == 1:
            pt = pb = pl = pr
            pad = f"{pl}px"
        elif form == 2:
            pb, pr = pt, pl
            pad = f"{pt}px {pl}px"
        elif form == 3:
            pr = pl
            pad = f"{pt}px {pl}px {pb}px"
        else:
            pad = f"{pt}px {pr}px {pb}px {pl}px"
        bw = rng.randint(1, 4)
        m = rng.choice([8, 10, 12, 16, 20])
        ask = rng.choice(["border", "content", "outer"])
        hor = pl + pr + 2 * bw

        def sizes(sz):
            cw = w if sz == "content-box" else w - hor
            return {"content": cw, "border": cw + hor, "outer": cw + hor + 2 * m}

        right = sizes(sizing)
        wrong = sizes("border-box" if sizing == "content-box" else "content-box")
        correct = right[ask]
        cands = [v for k, v in right.items() if k != ask] + [wrong[ask], w + pt + pb + 2 * bw,
                                                              right["content"] + pl + pr, right["border"] + m]
        if right["content"] > 0 and len({c for c in cands if c != correct}) >= 3:
            break
    what = {"border": "ширина элемента с учётом рамки (offsetWidth)",
            "content": "ширина области содержимого (content box)",
            "outer": "ширина места, которое элемент занимает по горизонтали вместе с margin"}[ask]
    cls = rng.choice(["card", "panel", "tile", "box"])
    code = (f".{cls} {{\n  box-sizing: {sizing};\n  width: {w}px;\n  padding: {pad};\n"
            f"  border: {bw}px solid #ccc;\n  margin: 0 {m}px;\n}}")
    return {
        "stem": f"Блочный элемент .{cls} находится в широком контейнере. Чему равна {what}, в пикселях?",
        "code": code,
        "code_lang": "css",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "При content-box width задаёт ширину содержимого, padding и border добавляются сверху; при "
                       "border-box width уже включает padding и border. margin в ширину элемента не входит.",
    }


@template(id="frontend.css_specificity", pool="frontend", topics=["css"], fmt="calc", a=1.3, b=0.4,
          title="Специфичность CSS-селекторов", variants=5000)
def _css_specificity(rng: random.Random) -> dict:
    nav = rng.choice(["menu", "header", "sidebar", "topbar"])
    eid = rng.choice(["home", "logo", "cta", "main-link"])
    c1 = rng.choice(["link", "item", "nav-link"])
    c2 = rng.choice(["active", "current", "selected"])
    sels = [
        (f"#{eid}", (1, 0, 0)), (f"a#{eid}", (1, 0, 1)), (f".{nav} #{eid}", (1, 1, 0)),
        (f".{c1}", (0, 1, 0)), (f".{c1}.{c2}", (0, 2, 0)), (f"a.{c2}", (0, 1, 1)), ("a", (0, 0, 1)),
        ("nav a", (0, 0, 2)), (f".{nav} a", (0, 1, 1)), (f".{nav} .{c1}", (0, 2, 0)),
        (f"nav > a.{c1}.{c2}", (0, 2, 2)), (f".{nav} a.{c1}", (0, 2, 1)), ("nav a[href]", (0, 1, 2)),
        ("[href]", (0, 1, 0)), (f"nav .{c2}", (0, 1, 1)), (f"a.{c1}:not(.{c2}-x)", (0, 2, 1)),
    ]
    colors = ["red", "green", "blue", "orange", "purple", "teal", "gray", "brown"]
    while True:
        rules = rng.sample(sels, 4)
        if rng.random() < 0.6:  # в большинстве экземпляров без id — сравнение классов и тегов
            rules = rng.sample([s for s in sels if s[1][0] == 0], 4)
        best = max(r[1] for r in rules)
        winners = [i for i, r in enumerate(rules) if r[1] == best]
        win = winners[-1]
        if win != 3 or len(winners) > 1:
            break
    cols = rng.sample(colors, 4)
    code_css = "\n".join(f"{r[0]} {{ color: {c}; }}" for r, c in zip(rules, cols))
    html = f'<nav class="{nav}">\n  <a id="{eid}" class="{c1} {c2}" href="/">Главная</a>\n</nav>'
    return {
        "stem": "Какой цвет текста получит ссылка? Стили подключены в указанном порядке, других стилей нет.",
        "code": f"<!-- HTML -->\n{html}\n\n<style>\n{code_css}\n</style>",
        "code_lang": "html",
        "correct": cols[win],
        "distractors": [c for i, c in enumerate(cols) if i != win],
        "explanation": "Побеждает селектор с наибольшей специфичностью (id, классы/атрибуты/псевдоклассы, теги); "
                       ":not() считается по аргументу; при равенстве — правило, объявленное позже. "
                       + "; ".join(f"{r[0]} = {r[1]}" for r in rules),
    }


# ---------------------------------------------------------------------------------------------- react

@template(id="frontend.react_batching", pool="frontend", topics=["react"], fmt="calc", a=1.4, b=0.7,
          title="Обновление состояния React: батчинг и updater-функции", variants=2000)
def _react_batching(rng: random.Random) -> dict:
    st, setter = rng.choice([("count", "setCount"), ("total", "setTotal"), ("score", "setScore"),
                             ("likes", "setLikes")])
    while True:
        init = rng.randint(0, 10)
        ups = [(rng.choice(["val", "fn"]), rng.randint(1, 5)) for _ in range(3)]
        if {u[0] for u in ups} != {"val", "fn"}:
            continue
        clicks = rng.choice([1, 1, 2])

        def apply(mode):
            s = init
            for _ in range(clicks):
                base = s
                for kind, k in ups:
                    if mode == "ok":
                        s = (base + k) if kind == "val" else (s + k)
                    elif mode == "all_fn":
                        s = s + k
                    elif mode == "all_val":
                        s = base + k
                if mode == "first":
                    s = base + ups[0][1]
            return s

        correct = apply("ok")
        cands = [apply("all_fn"), apply("all_val"), apply("first"), init + clicks, init + sum(k for _, k in ups)]
        if len({c for c in cands if c != correct}) >= 3:
            break
    lines = [f"  {setter}({st} + {k});" if kind == "val" else f"  {setter}((prev) => prev + {k});" for kind, k in ups]
    comp = rng.choice(["Counter", "LikeButton", "Score", "Clicker"])
    code = (f"function {comp}() {{\n  const [{st}, {setter}] = useState({init});\n\n"
            f"  const handleClick = () => {{\n" + "\n".join("  " + ln for ln in lines) + "\n  };\n\n"
            f"  return <button onClick={{handleClick}}>{{{st}}}</button>;\n}}")
    return {
        "stem": f"Какое число отобразит кнопка после {'одного клика' if clicks == 1 else 'двух кликов'}?",
        "code": code,
        "code_lang": "tsx",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": f"Внутри обработчика {st} — значение из текущего рендера (замыкание). Обновления "
                       f"ставятся в очередь и применяются по порядку: {setter}(x) заменяет состояние, "
                       f"{setter}(prev => …) берёт результат предыдущего обновления.",
    }


@template(id="frontend.react_bugs", pool="frontend", topics=["react"], fmt="bug", a=1.1, b=0.1,
          title="Типичные ошибки в React-компонентах", variants=80)
def _react_bugs(rng: random.Random) -> dict:
    variant = rng.randrange(6)
    if variant == 0:
        entity, field = rng.choice([("задача", "title"), ("покупка", "name"), ("письмо", "subject"),
                                    ("заметка", "text")])
        comp = rng.choice(["TodoList", "CartList", "Inbox", "Notes"])
        code = (f"function {comp}({{ items, onRemove }}) {{\n"
                f"  return items.map((item, index) => (\n"
                f"    <li key={{index}}>\n"
                f"      <input type=\"checkbox\" /> {{item.{field}}}\n"
                f"      <button onClick={{() => onRemove(item.id)}}>×</button>\n"
                f"    </li>\n  ));\n}}")
        return {"stem": f"Пользователь отметил чекбокс у первой строки ({entity}) и удалил её. Галочка "
                        f"«перескочила» на следующую строку. В чём причина?",
                "code": code, "code_lang": "tsx",
                "correct": "key={index}: после удаления состояние строк сопоставляется по позиции",
                "distractors": ["Неконтролируемый checkbox нельзя использовать внутри map",
                                "onRemove вызывается при рендере, а не по клику",
                                "Без React.memo строки списка теряют состояние"],
                "explanation": "Ключ должен быть стабильным идентификатором элемента (item.id), а не индексом."}
    if variant == 1:
        comp, row = rng.choice([("UsersTable", "user"), ("OrdersTable", "order"), ("FilesTable", "file")])
        code = (f"function {comp}({{ rows }}) {{\n"
                f"  return (\n    <table><tbody>\n"
                f"      {{rows.map(({row}) => (\n"
                f"        <EditableRow key={{Math.random()}} {row}={{{row}}} />\n"
                f"      ))}}\n    </tbody></table>\n  );\n}}")
        return {"stem": "При каждом обновлении родителя поля ввода в строках теряют фокус и введённый текст. "
                        "Почему?",
                "code": code, "code_lang": "tsx",
                "correct": "Случайный key: на каждый рендер строки размонтируются и создаются заново",
                "distractors": ["EditableRow нужно обернуть в React.memo — без этого теряется фокус",
                                f"Нельзя передавать объект {row} целиком через props",
                                "map нужно заменить на forEach"],
                "explanation": "Новый key при каждом рендере означает новый компонент: старый размонтируется."}
    if variant == 2:
        st, setter, val = rng.choice([("items", "setItems", "x"), ("tags", "setTags", "tag"),
                                      ("users", "setUsers", "user")])
        code = (f"const [{st}, {setter}] = useState([]);\n\n"
                f"const add = ({val}) => {{\n  {st}.push({val});\n  {setter}({st});\n}};")
        return {"stem": f"После вызова add(...) список {st} на экране не обновляется. Почему?",
                "code": code, "code_lang": "tsx",
                "correct": "Массив мутирован, ссылка не изменилась — React пропускает обновление",
                "distractors": [f"{setter} асинхронный, его нужно вызвать дважды",
                                "useState не умеет хранить массивы, нужен useReducer",
                                "Нужно вызвать forceUpdate после setState"],
                "explanation": f"Нужно создать новый массив: {setter}([...{st}, {val}])."}
    if variant == 3:
        st, setter = rng.choice([("sec", "setSec"), ("ticks", "setTicks"), ("elapsed", "setElapsed")])
        ms = rng.choice([500, 1000, 2000])
        code = (f"const [{st}, {setter}] = useState(0);\n\n"
                f"useEffect(() => {{\n"
                f"  const id = setInterval(() => {setter}({st} + 1), {ms});\n"
                f"  return () => clearInterval(id);\n}}, []);")
        return {"stem": "Счётчик показывает 1 и дальше не растёт. Почему?",
                "code": code, "code_lang": "tsx",
                "correct": f"Колбэк замкнул {st} = 0; нужно {setter}((v) => v + 1)",
                "distractors": ["clearInterval срабатывает сразу после первого тика",
                                "setInterval не работает внутри useEffect",
                                "Пустой массив зависимостей перезапускает эффект на каждом рендере"],
                "explanation": "Эффект выполнился один раз, и интервал всегда видит значение из первого рендера."}
    if variant == 4:
        status = rng.choice(["new", "paid", "shipped", "active"])
        fn, st = rng.choice([("fetchOrders", "Orders"), ("fetchUsers", "Users"), ("fetchTickets", "Tickets")])
        code = (f"const [list, setList] = useState([]);\n"
                f"const filter = {{ status: \"{status}\" }};\n\n"
                f"useEffect(() => {{\n  {fn}(filter).then(setList);\n}}, [filter]);")
        return {"stem": "Компонент бесконечно отправляет запросы на сервер. В чём причина?",
                "code": code, "code_lang": "tsx",
                "correct": "filter — новый объект на каждом рендере, эффект перезапускается",
                "distractors": [f"{fn} нужно вызывать через await внутри эффекта",
                                "then(setList) вызывает setList синхронно во время рендера",
                                "useEffect без функции очистки всегда выполняется бесконечно"],
                "explanation": "Зависимости сравниваются по ссылке; после setList новый рендер создаёт новый "
                               "filter, и эффект запускается снова. Помогут useMemo или примитив в зависимостях."}
    comp = rng.choice(["Title", "Badge", "Label", "Caption"])
    code = (f"function {comp}({{ value }}) {{\n"
            f"  const [text, setText] = useState(\"\");\n"
            f"  setText(value.trim());\n"
            f"  return <span>{{text}}</span>;\n}}")
    return {"stem": "Компонент падает с ошибкой «Too many re-renders». Почему?",
            "code": code, "code_lang": "tsx",
            "correct": "setText вызывается прямо в рендере и запускает новый рендер",
            "distractors": ["useState нельзя инициализировать пустой строкой",
                            "value.trim() каждый раз создаёт новую строку и ломает сравнение props",
                            "Хранить состояние может только классовый компонент"],
            "explanation": "Производное значение нужно вычислять в рендере без состояния: const text = value.trim()."}


@template(id="frontend.react_effect_order", pool="frontend", topics=["react"], fmt="output", a=1.2, b=1.6,
          title="Порядок рендера и эффектов в React", variants=3000)
def _react_effect_order(rng: random.Random) -> dict:
    c1, c2 = rng.choice([("Header", "Footer"), ("Sidebar", "Content"), ("Menu", "Page"), ("Avatar", "Stats")])
    while True:
        labels = iter(rng.sample([c.lower() for c in "abcdefghkmnprstxz"], 17))
        comps = {}
        for name in (c1, c2, "App"):
            comps[name] = {"body": next(labels) if rng.random() < 0.4 else None,
                           "layout": next(labels) if rng.random() < 0.5 else None,
                           "effect": next(labels) if rng.random() < 0.75 else None}
        logs = [v for c in comps.values() for v in c.values() if v]
        n_layout = sum(1 for c in comps.values() if c["layout"])
        n_effect = sum(1 for c in comps.values() if c["effect"])
        app_has_effect = comps["App"]["layout"] or comps["App"]["effect"]
        if not (4 <= len(logs) <= 6 and n_layout >= 1 and n_effect >= 2 and app_has_effect):
            continue
        pre, post = ["App", c1, c2], [c1, c2, "App"]

        def order(mode):
            out = []
            if mode == "interleave":  # эффекты сразу после рендера своего компонента
                for c in pre:
                    out += [comps[c][k] for k in ("body", "layout", "effect")]
                return [x for x in out if x]
            out += [comps[c]["body"] for c in pre]
            eff_order = pre if mode == "parent_first" else post
            if mode == "decl":
                for c in eff_order:
                    out += [comps[c][k] for k in comps[c]["_decl"]]
            else:
                out += [comps[c]["layout"] for c in eff_order]
                out += [comps[c]["effect"] for c in eff_order]
            return [x for x in out if x]

        for c in comps.values():
            hooks = [k for k in ("layout", "effect") if c[k]]
            rng.shuffle(hooks)
            c["_decl"] = hooks
        correct = order("ok")
        cands = [order("parent_first"), order("interleave"), order("decl")]
        if len({tuple(x) for x in cands} - {tuple(correct)}) >= 2:
            break
    cands += _swaps(correct, rng)
    # Запасные дистракторы: другие перестановки тех же сообщений (при 4 сообщениях swaps иногда совпадают)
    perms = [list(x) for x in itertools.islice(itertools.permutations(correct), 120)]
    rng.shuffle(perms)
    cands += perms

    def comp_code(name, children):
        c = comps[name]
        stmts = []
        for k in c["_decl"]:
            hook = "useLayoutEffect" if k == "layout" else "useEffect"
            stmts.append(f'  {hook}(() => console.log("{c[k]}"));')
        if c["body"]:
            stmts.insert(rng.randint(0, len(stmts)), f'  console.log("{c["body"]}");')
        stmts.append(f"  return {children};")
        return [f"function {name}() {{", *stmts, "}"]

    lines = comp_code(c1, "null") + comp_code(c2, "null") + comp_code("App", f"<><{c1} /><{c2} /></>")
    return {
        "stem": "Что появится в консоли при первом монтировании <App /> (React 18, без StrictMode)? "
                "(Сообщения через пробел в порядке вывода.)",
        "code": "\n".join(lines),
        "code_lang": "tsx",
        "correct": " ".join(correct),
        "distractors": [" ".join(c) for c in cands if c != correct],
        "explanation": "Рендер идёт сверху вниз (App, затем дети по порядку). В фазе commit сначала выполняются "
                       "все useLayoutEffect, затем все useEffect; и те и другие — от детей к родителю.",
    }


# ---------------------------------------------------------------------------------------------- typescript

@template(id="frontend.ts_type_errors", pool="frontend", topics=["typescript"], fmt="bug", a=1.3, b=1.1,
          title="Типизация TypeScript: сужение типов и совместимость", variants=400)
def _ts_type_errors(rng: random.Random) -> dict:
    variant = rng.randrange(7)
    nm = rng.choice(["p", "pt", "pos", "v"])
    if variant == 0:
        T, (k1, k2, k3) = rng.choice([("Point", ("x", "y", "z")), ("Size", ("w", "h", "d")),
                                      ("Range", ("from", "to", "step"))])
        a, b = rng.randint(1, 9), rng.randint(1, 9)
        stmts = [(f"const raw = {{ {k1}: {a}, {k2}: {b}, {k3}: 0 }};", None),
                 (f"const {nm}1: {T} = raw;", False),
                 (f"const {nm}2: {T} = {{ {k1}: {a}, {k2}: {b} }};", False),
                 (f"const {nm}3: {T} = {{ {k1}: {a}, {k2}: {b}, {k3}: 0 }};", True),
                 (f"const {nm}4 = {{ {k1}: {a}, {k2}: {b} }} as {T};", False)]
        head = [f"interface {T} {{ {k1}: number; {k2}: number }}", stmts[0][0]]
        body = stmts[1:]
        rng.shuffle(body)
        tail = []
        expl = "Проверка лишних свойств работает только для объектного литерала, присваиваемого напрямую; " \
               "переменная с лишним полем структурно совместима."
    elif variant == 1:
        f = rng.choice(["handle", "process", "parse"])
        head = [f"function {f}(a: any, u: unknown) {{"]
        body = [("  a.trim();", False), ('  if (typeof u === "string") u.trim();', False),
                ("  const n: number = a;", False), ("  u.trim();", True)]
        rng.shuffle(body)
        tail = ["}"]
        expl = "С unknown нельзя работать без сужения типа; any отключает проверки."
    elif variant == 2:
        f = rng.choice(["format", "show", "render"])
        head = [f"function {f}(v: string | number | null): string {{"]
        body = [("  const a = v?.toString();", False),
                ('  if (typeof v === "number") v.toFixed(1);', False),
                ("  const b = v.length;", True),
                ("  return String(v);", False)]
        tail = ["}"]
        expl = "Сужение внутри if действует только в его ветке; ниже v снова string | number | null."
    elif variant == 3:
        r, side = rng.choice([("r", "side"), ("radius", "size"), ("rad", "len")])
        head = [f'type Shape = {{ kind: "circle"; {r}: number }} | {{ kind: "square"; {side}: number }};',
                "function area(s: Shape): number {"]
        body = [("  const k = s.kind;", False),
                (f'  if (s.kind === "circle") return s.{r} * s.{r};', False),
                (f"  const x = s.{r};", True),
                (f"  return s.{side} * s.{side};", False)]
        tail = ["}"]
        expl = "После return в ветке circle тип s сужен до square, у которого нет поля " + r + "."
    elif variant == 4:
        a, b, c = rng.choice([("admin", "user", "guest"), ("draft", "live", "archived"), ("red", "green", "blue")])
        head = [f'const roles = ["{a}", "{b}"] as const;']
        body = [(f'const first: "{a}" = roles[0];', False), ("const list: string[] = [...roles];", False),
                (f'roles.push("{c}");', True), ("const n: number = roles.length;", False)]
        rng.shuffle(body)
        tail = []
        expl = "as const делает кортеж readonly — у него нет push."
    elif variant == 5:
        T, opt = rng.choice([("User", "email"), ("Profile", "phone"), ("Account", "nickname")])
        head = [f"interface {T} {{ name: string; {opt}?: string }}", f"function check(u: {T}) {{"]
        body = [("  const n: number = u.name.length;", False), (f"  const a = u.{opt}?.length;", False),
                (f'  const b: string = u.{opt} ?? "";', False), (f"  const c: number = u.{opt}.length;", True)]
        rng.shuffle(body)
        tail = ["}"]
        expl = f"Необязательное поле имеет тип string | undefined; без проверки u.{opt}.length — ошибка в strict."
    else:
        v1, v2 = rng.choice([("dark", "light"), ("asc", "desc"), ("on", "off"), ("ru", "en")])
        head = [f'type Mode = "{v1}" | "{v2}";', f'let mode = "{v1}";', f'const fixed = "{v2}";']
        body = [("const a: Mode = fixed;", False), ("const b: Mode = mode;", True),
                (f'const c: Mode = "{v1}";', False), ("const d: string = mode;", False)]
        rng.shuffle(body)
        tail = []
        expl = "let расширяет литерал до string, const сохраняет литеральный тип."
    lines = list(head)
    width = max(len(s) for s, _ in body) + 2
    err = None
    for i, (s, bad) in enumerate(body, 1):
        lines.append(f"{s.ljust(width)}// {i}")
        if bad:
            err = i
    lines += tail
    return {
        "stem": "В какой из пронумерованных строк компилятор TypeScript (strict: true) сообщит об ошибке?",
        "code": "\n".join(lines),
        "code_lang": "typescript",
        "correct": f"Строка {err}",
        "distractors": [f"Строка {i}" for i in range(1, 5) if i != err],
        "explanation": expl,
    }
