"""Пул шаблонов специализации «devops». Каждый шаблон регистрируется декоратором @template (см. base.py).

Ответы вычисляются в генераторах явной логикой (ipaddress для подсетей, модели перенаправлений и выбора
location в nginx); bash-шаблоны сверены прогоном сгенерированных команд в bash на зёрнах 0..49.
"""
import ipaddress
import math
import random
import re
from fractions import Fraction

from app.services.bank.base import template

_WORDS = ["start", "ready", "done", "fail", "retry", "warn", "ping", "sync", "load", "save"]


def _num(x) -> str:
    """Число без лишних нулей: 43.2, 1440, 0.5."""
    x = Fraction(x)
    if x.denominator == 1:
        return str(x.numerator)
    return f"{float(x):.6f}".rstrip("0").rstrip(".")


# ---------------------------------------------------------------------------------------------- linux / bash

@template(id="devops.chmod_octal", pool="devops", topics=["linux"], fmt="calc", a=1.1, b=-1.4,
          title="Права доступа Linux: восьмеричная и символьная запись", variants=300)
def _chmod_octal(rng: random.Random) -> dict:
    def rwx(d):
        return ("r" if d & 4 else "-") + ("w" if d & 2 else "-") + ("x" if d & 1 else "-")

    def rwx_rev(d):  # ошибка: перепутаны веса r и x
        return ("r" if d & 1 else "-") + ("w" if d & 2 else "-") + ("x" if d & 4 else "-")

    def rev_digit(d):
        return (d & 1) * 4 + (d & 2) + (d & 4) // 4

    while True:
        u = rng.choice([7, 7, 6, 6, 5, 4])
        g = rng.choice([7, 6, 5, 4, 0, 5, 4])
        o = rng.choice([5, 4, 0, 1, 0, 4])
        if len({u, g, o}) >= 2 and u != o:
            break
    kind = rng.choice(["-", "-", "d"])
    owner = rng.choice(["deploy", "www", "app", "ci"])
    fname = rng.choice(["run.sh", "deploy.sh", "config.yml", "backup.tar", "data"]) if kind == "-" else \
        rng.choice(["logs", "releases", "shared", "cache"])
    octal = f"{u}{g}{o}"
    sym = kind + rwx(u) + rwx(g) + rwx(o)
    if rng.random() < 0.5:
        size = rng.randint(1, 9) * 512
        code = f"$ ls -ld {fname}\n{sym} 1 {owner} {owner} {size} Mar {rng.randint(1, 28)} 10:15 {fname}"
        bits = "".join(str(bin(d).count("1")) for d in (u, g, o))
        cands = ["".join(str(rev_digit(d)) for d in (u, g, o)), f"{o}{g}{u}", bits, f"{u}{o}{g}",
                 f"{u}{g ^ 1}{o}", f"{u ^ 2}{g}{o}", f"{u}{g}{o ^ 4}"]
        return {
            "stem": "Какие права у объекта в восьмеричной записи (как для chmod)?",
            "code": code, "code_lang": "bash",
            "correct": octal,
            "distractors": cands,
            "explanation": "r = 4, w = 2, x = 1; цифры — владелец, группа, остальные. " + f"{sym[1:]} = {octal}.",
        }
    code = f"$ chmod {octal} {fname}\n$ ls -ld {fname}"
    cands = [kind + rwx_rev(u) + rwx_rev(g) + rwx_rev(o), kind + rwx(o) + rwx(g) + rwx(u),
             kind + rwx(u) + rwx(o) + rwx(g), kind + rwx(u) + rwx(g ^ 1) + rwx(o),
             kind + rwx(u ^ 2) + rwx(g) + rwx(o), kind + rwx(u) + rwx(g) + rwx(o ^ 4)]
    return {
        "stem": "Как будет выглядеть строка прав в выводе ls -ld после этой команды?",
        "code": code, "code_lang": "bash",
        "correct": sym,
        "distractors": cands,
        "explanation": "Каждая цифра — сумма r = 4, w = 2, x = 1 для владельца, группы и остальных.",
    }


def _bash_cond(rng: random.Random) -> tuple[str, bool]:
    kind = rng.choice(["true", "false", "gt", "lt", "eq", "ne", "num"])
    if kind == "true":
        return "true", True
    if kind == "false":
        return "false", False
    a, b = rng.randint(1, 9), rng.randint(1, 9)
    if kind == "num":
        kind = rng.choice(["gt", "lt"])
    op = {"gt": "-gt", "lt": "-lt", "eq": "-eq", "ne": "-ne"}[kind]
    res = {"gt": a > b, "lt": a < b, "eq": a == b, "ne": a != b}[kind]
    return f"[ {a} {op} {b} ]", res


@template(id="devops.bash_and_or", pool="devops", topics=["bash", "linux"], fmt="output", a=1.2, b=-1.2,
          title="Коды возврата и операторы && / || в bash", variants=3000)
def _bash_and_or(rng: random.Random) -> dict:
    def ev(lines, mode):
        out = []
        for stmt in lines:  # stmt: список элементов (op, cmd); cmd = ("c", text, bool) | ("e", label)
            if mode == "clike":  # ошибка: && связывает сильнее, чем || (как в C)
                groups, cur = [], []
                for op, cmd in stmt:
                    if op == "||":
                        groups.append(cur)
                        cur = []
                    cur.append(cmd)
                groups.append(cur)
                for grp in groups:
                    ok = True
                    for cmd in grp:
                        if cmd[0] == "e":
                            out.append(cmd[1])
                        elif not cmd[2]:
                            ok = False
                            break
                    if ok:
                        break
                continue
            status = 0
            for op, cmd in stmt:
                if op == "&&" and status != 0 or op == "||" and status == 0:
                    continue
                if cmd[0] == "e":
                    out.append(cmd[1])
                    status = 0
                else:
                    res = cmd[2] if mode != "invert" else not cmd[2]
                    status = 0 if res else 1
        return out

    while True:
        labels = iter(rng.sample(list("ABCDEFGHKMPRSTXZ"), 16))
        n = rng.choice([2, 3])
        pats = ["or_and"] + [rng.choice(["and_or", "or_and", "and_and_or", "or_semi"]) for _ in range(n - 1)]
        rng.shuffle(pats)
        lines, stmts = [], []
        for p in pats:
            ctext, cval = _bash_cond(rng)
            x, y = next(labels), next(labels)
            if p == "and_or":
                lines.append([[(None, ("c", ctext, cval)), ("&&", ("e", x)), ("||", ("e", y))]])
                stmts.append(f"{ctext} && echo {x} || echo {y}")
            elif p == "or_and":
                lines.append([[(None, ("c", ctext, cval)), ("||", ("e", x)), ("&&", ("e", y))]])
                stmts.append(f"{ctext} || echo {x} && echo {y}")
            elif p == "and_and_or":
                c2text, c2val = _bash_cond(rng)
                lines.append([[(None, ("c", ctext, cval)), ("&&", ("c", c2text, c2val)), ("||", ("e", x))]])
                stmts.append(f"{ctext} && {c2text} || echo {x}")
            else:
                lines.append([[(None, ("c", ctext, cval)), ("||", ("e", x))], [(None, ("e", y))]])
                stmts.append(f"{ctext} || echo {x}; echo {y}")
        flat = [s for ln in lines for s in ln]
        correct = ev(flat, "ok")
        cands = [ev(flat, "clike"), ev(flat, "invert")]
        if correct and len({tuple(c) for c in cands} - {tuple(correct)}) >= 1:
            break
    pool = [" ".join(c) or "(ничего)" for c in cands]
    for _ in range(10):
        drop = list(correct)
        if len(drop) > 1:
            drop.pop(rng.randrange(len(drop)))
            pool.append(" ".join(drop))
        extra = list(correct)
        extra.insert(rng.randrange(len(extra) + 1), rng.choice([lab for ln in lines for st in ln for _, c in st
                                                                 if c[0] == "e" for lab in [c[1]]]))
        pool.append(" ".join(extra))
    return {
        "stem": "Что выведет этот скрипт? (Строки вывода через пробел.)",
        "code": "#!/bin/bash\n" + "\n".join(stmts),
        "code_lang": "bash",
        "correct": " ".join(correct),
        "distractors": pool,
        "explanation": "В bash && и || имеют одинаковый приоритет и выполняются слева направо: команда после && "
                       "запускается, если предыдущая завершилась с кодом 0, после || — если с ненулевым. "
                       "Пропущенная команда не меняет код возврата; echo всегда возвращает 0.",
    }


@template(id="devops.text_pipeline", pool="devops", topics=["bash", "linux"], fmt="output", a=1.2, b=-0.5,
          title="Конвейеры обработки текста: sort, uniq, awk", variants=2000)
def _text_pipeline(rng: random.Random) -> dict:
    variant = rng.randrange(3)
    if variant == 0:
        while True:
            ips = [f"10.0.{rng.randint(0, 3)}.{rng.randint(2, 30)}" for _ in range(4)]
            if len(set(ips)) < 4:
                continue
            counts = rng.sample([1, 1, 2, 3, 4], 4)
            if counts.count(max(counts)) > 1:
                continue
            rows = [ip for ip, c in zip(ips, counts) for _ in range(c)]
            if not 6 <= len(rows) <= 9:
                continue
            rng.shuffle(rows)
            break
        paths = ["/", "/login", "/api/items", "/health"]
        log = [f"{ip} GET {rng.choice(paths)} {rng.choice([200, 200, 304, 404, 500])}" for ip in rows]
        best = ips[counts.index(max(counts))]
        second = sorted(zip(counts, ips))[-2][1]
        cmd = "awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -1 | awk '{print $2}'"
        cands = [second, rows[0], rows[-1], *ips]
        correct = best
        expl = "uniq -c считает подряд идущие одинаковые строки (поэтому перед ним sort), sort -rn ставит " \
               "самую частую первой."
    elif variant == 1:
        while True:
            paths = rng.sample(["/", "/login", "/api/items", "/api/cart", "/health", "/search", "/profile"], 5)
            log = []
            for _ in range(rng.randint(7, 9)):
                log.append(f"10.0.0.{rng.randint(2, 9)} GET {rng.choice(paths)} "
                           f"{rng.choice([200, 200, 301, 404, 403, 500, 502])}")
            err = [ln.split()[2] for ln in log if int(ln.split()[3]) >= 400]
            correct = str(len(set(err)))
            cands = [str(len(err)), str(len({ln.split()[2] for ln in log})),
                     str(len({ln.split()[2] for ln in log if int(ln.split()[3]) >= 500})),
                     str(sum(1 for ln in log if int(ln.split()[3]) < 400)), str(len(set(err)) + 1),
                     str(len(set(err)) - 1)]
            if 2 <= len(set(err)) and len(set(cands) - {correct}) >= 3:
                break
        cmd = "awk '$4 >= 400 {print $3}' access.log | sort -u | wc -l"
        expl = "awk отбирает строки с кодом ≥ 400 и печатает путь, sort -u оставляет уникальные, wc -l считает их."
    else:
        while True:
            names = rng.sample(["anna", "boris", "vera", "gleb", "dina", "egor", "ira", "oleg"], 5)
            vals = rng.sample([7, 8, 9, 12, 15, 21, 30, 45, 64, 88, 105, 120, 250], 5)
            lex = sorted(zip(names, vals), key=lambda p: str(p[1]))
            num = sorted(zip(names, vals), key=lambda p: p[1])
            if lex[-1] != num[-1] and lex[0] != num[0]:
                break
        log = [f"{n} {v}" for n, v in zip(names, vals)]
        if rng.random() < 0.5:
            cmd, correct = "sort -k2 scores.txt | tail -1 | cut -d' ' -f1", lex[-1][0]
            cands = [num[-1][0], num[0][0], lex[0][0], *names]
        else:
            cmd, correct = "sort -k2 scores.txt | head -1 | cut -d' ' -f1", lex[0][0]
            cands = [num[0][0], num[-1][0], lex[-1][0], *names]
        expl = "Без -n sort сравнивает строки посимвольно: «105» < «12» < «7». Для чисел нужен sort -k2 -n."
    fname = "scores.txt" if variant == 2 else "access.log"
    code = f"$ cat {fname}\n" + "\n".join(log) + f"\n$ {cmd}"
    return {
        "stem": "Что выведет последняя команда?",
        "code": code,
        "code_lang": "bash",
        "correct": correct,
        "distractors": cands,
        "explanation": expl,
    }


@template(id="devops.redirects", pool="devops", topics=["bash", "linux"], fmt="output", a=1.3, b=0.4,
          title="Перенаправление потоков stdout / stderr", variants=2000)
def _redirects(rng: random.Random) -> dict:
    labels = rng.sample(_WORDS, 3)
    streams = rng.choice([[1, 1, 2], [1, 2, 2], [2, 1, 1], [1, 2, 1], [2, 1, 2]])
    script = list(zip(streams, labels))
    f = rng.choice(["log.txt", "out.log", "run.log"])
    forms = [
        (f"./app.sh > {f} 2>&1", [">f", "2>&1"], None),
        (f"./app.sh 2>&1 > {f}", ["2>&1", ">f"], None),
        (f"./app.sh 2> {f}", ["2>f"], None),
        (f"./app.sh &> {f}", ["&>f"], None),
        (f"./app.sh > /dev/null 2> {f}", [">null", "2>f"], None),
        ("./app.sh 2>&1 1>/dev/null", ["2>&1", ">null"], None),
        ("./app.sh 2>&1 | grep -v {X}", ["2>&1"], "pipe"),
        (f"./app.sh 2> {f} | grep -v {{X}}", ["2>f"], "pipe"),
    ]
    cmd, redirs, pipe = rng.choice(forms)

    def run(redirs, pipe, mode="ok"):
        fd = {1: "pipe" if pipe else "tty", 2: "tty"}
        rs = list(redirs)
        if mode == "order_free":  # ошибка: «2>&1 означает туда же, куда в итоге stdout»
            rs = [r for r in rs if r != "2>&1"] + (["2>&1"] if "2>&1" in rs else [])
        if mode == "ignore_dup":
            rs = [r for r in rs if r != "2>&1"]
        for r in rs:
            if r == ">f":
                fd[1] = "file"
            elif r == ">null":
                fd[1] = "null"
            elif r == "2>&1":
                fd[2] = fd[1]
            elif r == "2>f":
                fd[2] = "file"
            elif r == "&>f":
                fd[1] = fd[2] = "file"
        res = {"tty": [], "file": [], "pipe": [], "null": []}
        for s, lab in script:
            res[fd[s]].append(lab)
        return res

    x = None
    if pipe:
        through = run(redirs, pipe)["pipe"]
        x = rng.choice(through)
        cmd = cmd.replace("{X}", x)

    def view(res, where):
        lst = res[where]
        if where == "tty" and pipe:
            lst = lst + [lab for lab in res["pipe"] if lab != x]
        return " ".join(lst) or "(ничего)"

    has_file = any(r in (">f", "2>f", "&>f") for r in redirs)
    where = "file" if has_file and rng.random() < 0.5 else "tty"
    correct = view(run(redirs, pipe), where)
    cands = [view(run(redirs, pipe, "order_free"), where), view(run(redirs, pipe, "ignore_dup"), where),
             " ".join(labels), "(ничего)",
             " ".join(lab for s, lab in script if s == 1), " ".join(lab for s, lab in script if s == 2)]
    if pipe:
        cands.append(" ".join(labels))
        cands.append(" ".join(lab for lab in labels if lab != x))
    q = "Что будет выведено в терминал?" if where == "tty" else f"Что окажется в файле {f}?"
    code = "$ cat app.sh\n#!/bin/sh\n" + "\n".join(
        f"echo {lab}" if s == 1 else f"echo {lab} >&2" for s, lab in script) + f"\n$ {cmd}"
    return {
        "stem": f"{q} (Строки через пробел в порядке вывода; файла до запуска не было.)",
        "code": code,
        "code_lang": "bash",
        "correct": correct,
        "distractors": [c for c in cands if c],
        "explanation": "Перенаправления применяются слева направо: 2>&1 копирует текущий на этот момент "
                       "адресат stdout. Поэтому «> f 2>&1» пишет оба потока в файл, а «2>&1 > f» отправляет "
                       "stderr туда, куда stdout указывал раньше (терминал или канал).",
    }


@template(id="devops.cron_schedule", pool="devops", topics=["linux"], fmt="calc", a=1.3, b=-0.3,
          title="Расписание cron", variants=3000)
def _cron_schedule(rng: random.Random) -> dict:
    while True:
        mk = rng.choice(["step", "step", "list", "fixed"])
        if mk == "step":
            m = rng.choice([5, 10, 15, 20, 30, 25, 40, 45])
            mf, mc, mc_alt = f"*/{m}", len(range(0, 60, m)), 60 // m
        elif mk == "list":
            a = rng.randint(0, 29)
            mf, mc, mc_alt = f"{a},{a + 30}", 2, 1
        else:
            a = rng.randint(0, 59)
            mf, mc, mc_alt = str(a), 1, 60
        hk = rng.choice(["range", "range", "step", "list"])
        if hk == "range":
            h1 = rng.randint(6, 10)
            h2 = h1 + rng.randint(4, 10)
            hf, hc, hc_alt = f"{h1}-{h2}", h2 - h1 + 1, h2 - h1
        elif hk == "step":
            h = rng.choice([2, 3, 4, 5, 6, 7, 8])
            hf, hc, hc_alt = f"*/{h}", len(range(0, 24, h)), 24 // h
            if hc == hc_alt:
                hc_alt = hc + 1
        else:
            hs = sorted(rng.sample(range(7, 23), 3))
            hf, hc, hc_alt = ",".join(map(str, hs)), 3, hs[-1] - hs[0] + 1
        dk = rng.choice(["1-5", "1-5", "*", "1,3,5", "6,0"])
        dc = {"1-5": 5, "*": 7, "1,3,5": 3, "6,0": 2}[dk]
        dc_alt = {"1-5": 4, "*": 5, "1,3,5": 2, "6,0": 1}[dk]
        ask = rng.choice(["week", "week", "wed"])
        if ask == "week":
            correct = mc * hc * dc
            cands = [mc_alt * hc * dc, mc * hc_alt * dc, mc * hc * dc_alt, mc * hc, mc * hc * 7]
        else:
            runs_wed = dk in ("1-5", "*", "1,3,5")
            correct = mc * hc if runs_wed else 0
            cands = [mc_alt * hc, mc * hc_alt, mc * hc * dc, mc * hc if not runs_wed else 0, mc * 24]
        if correct > 0 and len(set(cands) - {correct}) >= 3 or ask == "wed" and len(set(cands) - {correct}) >= 3:
            break
    script = rng.choice(["backup.sh", "cleanup.sh", "report.py", "sync.sh"])
    q = "за полную неделю (с понедельника по воскресенье)" if ask == "week" else "за одну среду (сутки)"
    return {
        "stem": f"Сколько раз задача из crontab запустится {q}?",
        "code": f"# m h dom mon dow  command\n{mf} {hf} * * {dk}  /opt/jobs/{script}",
        "code_lang": "bash",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "Поля: минута, час, день месяца, месяц, день недели (0 — воскресенье). */N — значения "
                       "0, N, 2N… в пределах поля (не обязательно делит его нацело), диапазон a-b включает обе "
                       "границы. Итог = число минут × число часов × число подходящих дней.",
    }


# ---------------------------------------------------------------------------------------------- networking

def _rand_private(rng: random.Random) -> str:
    first = rng.choice([10, 172, 192])
    second = {10: rng.randint(0, 255), 172: rng.randint(16, 31), 192: 168}[first]
    return f"{first}.{second}.{rng.randint(0, 255)}.{rng.randint(0, 255)}"


@template(id="devops.cidr_hosts", pool="devops", topics=["networking"], fmt="calc", a=1.3, b=-0.4,
          title="Размер подсети и маска по CIDR", variants=400)
def _cidr_hosts(rng: random.Random) -> dict:
    p = rng.randint(20, 29)
    net = ipaddress.ip_network(f"{_rand_private(rng)}/{p}", strict=False)
    if rng.random() < 0.6:
        hosts = 2 ** (32 - p) - 2
        return {
            "stem": f"Сколько адресов можно назначить хостам в подсети {net}?",
            "code": None,
            "correct": str(hosts),
            "distractors": [str(2 ** (32 - p)), str(2 ** (33 - p) - 2), str(2 ** (31 - p) - 2), str(2 ** (32 - p) - 1)],
            "explanation": f"2^(32−{p}) = {2 ** (32 - p)} адресов, минус адрес сети и широковещательный.",
        }

    def mask(q):
        return str(ipaddress.ip_network(f"0.0.0.0/{q}").netmask)

    return {
        "stem": f"Какая маска подсети в десятичной записи соответствует {net}?",
        "code": None,
        "correct": mask(p),
        "distractors": [mask(p - 1), mask(p + 1), mask(p - 2), mask(p + 2)],
        "explanation": f"/{p} — первые {p} бит маски единичные.",
    }


@template(id="devops.cidr_membership", pool="devops", topics=["networking"], fmt="calc", a=1.4, b=0.6,
          title="Принадлежность адреса подсети, broadcast", variants=3000)
def _cidr_membership(rng: random.Random) -> dict:
    p = rng.randint(18, 27)
    net = ipaddress.ip_network(f"{_rand_private(rng)}/{p}", strict=False)
    size = net.num_addresses
    host = net.network_address + rng.randint(1, size - 2)
    if rng.random() < 0.5:
        outs = [net.broadcast_address + rng.randint(1, 3), net.network_address - rng.randint(1, 3),
                ipaddress.ip_address(int(host) ^ (1 << (32 - p))), ipaddress.ip_address(int(host) ^ (1 << (33 - p))),
                ipaddress.ip_address(int(host) ^ (1 << (34 - p))), net.broadcast_address + 1 + size // 2]
        return {
            "stem": f"Какой из адресов принадлежит подсети {net}?",
            "code": None,
            "correct": str(host),
            "distractors": [str(a) for a in outs if a not in net],
            "explanation": f"Подсеть {net} охватывает {net.network_address} – {net.broadcast_address}.",
        }

    def bc(q):
        return str(ipaddress.ip_network(f"{host}/{q}", strict=False).broadcast_address)

    h = str(host).split(".")
    cands = [bc(p + 1), bc(p - 1), str(net.network_address), ".".join(h[:3] + ["255"]), bc(p + 2), bc(p - 2),
             str(net.broadcast_address - 1), str(net.broadcast_address + 1)]
    return {
        "stem": f"Интерфейсу назначен адрес {host}/{p}. Какой широковещательный (broadcast) адрес у его подсети?",
        "code": None,
        "correct": str(net.broadcast_address),
        "distractors": cands,
        "explanation": f"Сеть {net}: последний адрес диапазона — {net.broadcast_address}.",
    }


@template(id="devops.http_status_proxy", pool="devops", topics=["http", "nginx"], fmt="concept", a=1.1, b=-0.6,
          title="Коды ответа HTTP за обратным прокси", variants=100)
def _http_status_proxy(rng: random.Random) -> dict:
    port = rng.choice([3000, 5000, 8000, 8080, 9000])
    up = rng.choice(["app", "api", "backend", "web"])
    variant = rng.randrange(7)
    codes = {"502": "502 Bad Gateway", "503": "503 Service Unavailable", "504": "504 Gateway Timeout",
             "500": "500 Internal Server Error", "413": "413 Content Too Large", "403": "403 Forbidden",
             "404": "404 Not Found", "400": "400 Bad Request", "429": "429 Too Many Requests",
             "408": "408 Request Timeout", "401": "401 Unauthorized", "301": "301 Moved Permanently"}
    if variant == 0:
        stem = f"nginx проксирует запросы на {up}:{port}, но процесс приложения упал и порт никто не слушает. " \
               f"Что получит клиент?"
        c, d = "502", ["504", "503", "500"]
    elif variant == 1:
        t = rng.choice([30, 60, 90])
        stem = f"Приложение за nginx отвечает на тяжёлый отчёт дольше {t} с, а proxy_read_timeout {t}s. " \
               f"Что получит клиент?"
        c, d = "504", ["502", "408", "500"]
    elif variant == 2:
        mb = rng.choice([1, 5, 10, 20])
        stem = f"Пользователь загружает файл {mb * 3} МБ, в nginx задано client_max_body_size {mb}m. " \
               f"Что получит клиент?"
        c, d = "413", ["400", "403", "500"]
    elif variant == 3:
        r = rng.choice([5, 10, 20])
        stem = f"В nginx настроен limit_req (rate={r}r/s, без limit_req_status). Клиент превысил лимит. " \
               f"Какой код ответа он получит по умолчанию?"
        c, d = "503", ["429", "403", "502"]
    elif variant == 4:
        stem = "В location /admin/ стоит deny all; запрос пришёл с адреса, не входящего в allow. " \
               "Что получит клиент?"
        c, d = "403", ["401", "404", "400"]
    elif variant == 5:
        stem = f"Сервер слушает 443 с ssl, а клиент отправил обычный HTTP-запрос на порт 443 " \
               f"(http://{up}.test:443/). Что ответит nginx?"
        c, d = "400", ["301", "502", "403"]
    else:
        stem = f"Приложение на {up}:{port} получило запрос и упало с необработанным исключением, вернув " \
               f"ответ с ошибкой. Какой код, скорее всего, увидит клиент?"
        c, d = "500", ["502", "503", "504"]
    return {
        "stem": stem,
        "code": None,
        "correct": codes[c],
        "distractors": [codes[x] for x in d],
        "explanation": "502 — прокси не смог получить корректный ответ (upstream недоступен), 504 — upstream не "
                       "ответил за таймаут, 413 — тело больше лимита, limit_req по умолчанию отвечает 503, "
                       "deny — 403, HTTP на HTTPS-порт — 400.",
    }


# ---------------------------------------------------------------------------------------------- docker / git

@template(id="devops.docker_ports", pool="devops", topics=["docker", "networking"], fmt="concept", a=1.1, b=-0.9,
          title="Публикация портов и сеть в Docker", variants=400)
def _docker_ports(rng: random.Random) -> dict:
    cport = rng.choice([80, 3000, 5000, 8000, 8080])
    hport = rng.choice([8081, 8888, 9090, 18080, 3001])
    name = rng.choice(["web", "api", "shop", "admin"])
    variant = rng.randrange(4)
    if variant == 0:
        return {
            "stem": f"Приложение в контейнере слушает 0.0.0.0:{cport}. По какому адресу открыть его в браузере "
                    f"на этой же машине?",
            "code": f"docker run -d --name {name} -p {hport}:{cport} {name}-image:1.4",
            "code_lang": "bash",
            "correct": f"http://localhost:{hport}",
            "distractors": [f"http://localhost:{cport}", f"http://{name}:{hport}", f"http://{name}:{cport}"],
            "explanation": "-p HOST:CONTAINER — слева порт хоста, справа порт внутри контейнера.",
        }
    if variant == 1:
        db_h, db_c = rng.choice([(15432, 5432), (25432, 5432), (13306, 3306), (16379, 6379)])
        svc = {5432: "db", 3306: "mysql", 6379: "cache"}[db_c]
        img = {5432: "postgres:16", 3306: "mysql:8.4", 6379: "redis:7"}[db_c]
        return {
            "stem": f"Сервис {name} в том же compose-проекте подключается к {svc}. Какой адрес указать в его "
                    f"настройках?",
            "code": f"services:\n  {svc}:\n    image: {img}\n    ports:\n      - \"{db_h}:{db_c}\"\n"
                    f"  {name}:\n    build: .\n    depends_on: [{svc}]",
            "code_lang": "yaml",
            "correct": f"{svc}:{db_c}",
            "distractors": [f"localhost:{db_h}", f"{svc}:{db_h}", f"localhost:{db_c}"],
            "explanation": "Внутри compose-сети контейнеры обращаются друг к другу по имени сервиса и порту "
                           "контейнера; проброс ports нужен только для доступа с хоста.",
        }
    if variant == 2:
        return {
            "stem": f"Контейнер запущен так. Коллега с другого компьютера в той же сети не может открыть "
                    f"http://<ip-хоста>:{hport}. Почему?",
            "code": f"docker run -d --name {name} -p 127.0.0.1:{hport}:{cport} {name}-image:1.4",
            "code_lang": "bash",
            "correct": "Порт опубликован только на loopback-интерфейсе хоста",
            "distractors": [f"Нужно ещё добавить EXPOSE {hport} в Dockerfile",
                            f"Контейнер слушает {cport}, а снаружи нужно обращаться к {cport}",
                            "Docker по умолчанию запрещает доступ к контейнерам извне"],
            "explanation": "Адрес перед портами задаёт интерфейс хоста, на котором открывается порт.",
        }
    return {
        "stem": f"В Dockerfile есть EXPOSE {cport}, контейнер запущен без флагов -p/-P. Что верно?",
        "code": f"docker run -d --name {name} {name}-image:1.4",
        "code_lang": "bash",
        "correct": f"Порт {cport} не опубликован на хосте, EXPOSE лишь документирует его",
        "distractors": [f"Сервис доступен на http://localhost:{cport}",
                        "Docker опубликует порт на случайном порту хоста",
                        f"Сервис доступен на http://localhost:{cport} только из-под root"],
        "explanation": "Публикацию порта делают -p (явно) или -P (все EXPOSE на случайные порты).",
    }


@template(id="devops.dockerfile_cache", pool="devops", topics=["docker", "ci_cd"], fmt="concept", a=1.3, b=0.5,
          title="Кэш слоёв при сборке Docker-образа", variants=60)
def _dockerfile_cache(rng: random.Random) -> dict:
    stacks = {
        "python": ("FROM python:3.12-slim", "COPY requirements.txt .", "RUN pip install -r requirements.txt",
                   "RUN python -m compileall .", 'CMD ["python", "main.py"]', "requirements.txt",
                   rng.choice(["app/handlers.py", "app/models.py", "main.py"])),
        "node": ("FROM node:20-alpine", "COPY package.json package-lock.json ./", "RUN npm ci",
                 "RUN npm run build", 'CMD ["node", "dist/index.js"]', "package-lock.json",
                 rng.choice(["src/index.ts", "src/routes.ts", "src/db.ts"])),
        "go": ("FROM golang:1.22", "COPY go.mod go.sum ./", "RUN go mod download",
               "RUN go build -o /bin/app ./cmd/app", 'CMD ["/bin/app"]', "go.sum",
               rng.choice(["internal/handler.go", "cmd/app/main.go", "internal/store.go"])),
    }
    frm, copy_dep, install, build, cmd, manifest, src = stacks[rng.choice(list(stacks))]
    layout = rng.choice(["good", "bad"])
    if layout == "good":
        lines = [frm, "WORKDIR /app", copy_dep, install, "COPY . .", build, cmd]
    else:
        lines = [frm, "WORKDIR /app", "COPY . .", install, build, cmd]
    ignored = rng.choice(["README.md", "docs/architecture.md", ".git/"])
    change = rng.choice(["manifest", "src", "src", "ignored"])
    changed = {"manifest": manifest, "src": src, "ignored": ignored.rstrip("/") + ("/HEAD" if ignored == ".git/" else "")}[change]
    if change == "ignored":
        correct = "Ни с какой: все шаги возьмутся из кэша"
    elif change == "manifest" and layout == "good":
        correct = copy_dep
    else:
        correct = "COPY . ."
    cands = [ln for ln in lines if ln not in (correct, "WORKDIR /app")]
    rng.shuffle(cands)
    cands = [install] + cands
    if correct != "Ни с какой: все шаги возьмутся из кэша":
        cands.insert(1, "Ни с какой: все шаги возьмутся из кэша")
    if correct in cands:
        cands.remove(correct)
    return {
        "stem": f"Образ уже собирался раньше. Затем изменили только файл {changed} и снова запустили docker build. "
                f"Начиная с какой инструкции кэш слоёв перестанет использоваться? (.dockerignore: .git, "
                f"README.md, docs/)",
        "code": "\n".join(lines),
        "code_lang": "dockerfile",
        "correct": correct,
        "distractors": cands,
        "explanation": "COPY/ADD инвалидируются при изменении содержимого копируемых файлов, RUN — при изменении "
                       "текста команды или любого предыдущего слоя. Файлы из .dockerignore не попадают в контекст "
                       "и на кэш не влияют. Поэтому манифест зависимостей копируют и устанавливают до COPY . .",
    }


@template(id="devops.git_history", pool="devops", topics=["git"], fmt="calc", a=1.2, b=0.3,
          title="Git: merge, rebase и диапазоны коммитов", variants=500)
def _git_history(rng: random.Random) -> dict:
    while True:
        n, m = rng.randint(2, 7), rng.randint(2, 7)
        if n != m:
            break
    br = rng.choice(["feature/login", "feature/cart", "fix/timeout", "feature/export"])
    base = rng.choice(["main", "develop"])
    ctx = (f"Ветка {br} ответвилась от {base}. С тех пор число новых коммитов в {base} — {n}, "
           f"в {br} — {m}. Слияний между ветками не было.")
    variant = rng.randrange(6)
    if variant == 0:
        q, cmd, c = "Сколько строк выведет команда?", f"git log --oneline {base}..{br}", m
    elif variant == 1:
        q, cmd, c = "Сколько строк выведет команда?", f"git log --oneline {br}..{base}", n
    elif variant == 2:
        q, cmd, c = "Сколько коммитов получат новые хеши после команды?", f"git switch {br}\ngit rebase {base}", m
    elif variant == 3:
        q, cmd, c = ("Сколько новых коммит-объектов будет создано?", f"git switch {base}\ngit merge --no-ff {br}", 1)
    elif variant == 4:
        q, cmd, c = (f"Сколько коммитов выведет git log --oneline {base}..{br} после этих команд?",
                     f"git switch {br}\ngit rebase {base}", m)
    else:
        k = rng.randint(1, m - 1)
        q, cmd, c = (f"Сколько строк выведет git log --oneline {base}..{br} после этих команд?",
                     f"git switch {br}\ngit reset --soft HEAD~{k}\ngit commit -m \"squash\"", m - k + 1)
    cands = [n, m, n + m, m + 1, 1, 0, n + 1, m - 1]
    return {
        "stem": f"{ctx} {q}",
        "code": cmd,
        "code_lang": "bash",
        "correct": str(c),
        "distractors": [str(x) for x in cands if x != c],
        "explanation": "A..B — коммиты, достижимые из B, но не из A. rebase пересоздаёт каждый коммит ветки "
                       "(новые хеши), merge --no-ff создаёт один merge-коммит, reset --soft + commit "
                       "сворачивает последние коммиты в один.",
    }


# ---------------------------------------------------------------------------------------------- kubernetes

@template(id="devops.k8s_probes_resources", pool="devops", topics=["kubernetes"], fmt="concept", a=1.2, b=0.7,
          title="Kubernetes: пробы, requests и limits", variants=300)
def _k8s_probes_resources(rng: random.Random) -> dict:
    app = rng.choice(["orders", "billing", "catalog", "auth"])
    variant = rng.randrange(6)
    if variant in (0, 1, 2):
        req_m, lim_m = rng.choice([(256, 512), (512, 1024), (128, 256), (300, 600)])
        req_c, lim_c = rng.choice([(250, 500), (100, 200), (500, 1000), (200, 400)])
        code = (f"containers:\n  - name: {app}\n    resources:\n      requests:\n        cpu: \"{req_c}m\"\n"
                f"        memory: \"{req_m}Mi\"\n      limits:\n        cpu: \"{lim_c}m\"\n        memory: \"{lim_m}Mi\"")
        if variant == 0:
            use = lim_m + rng.choice([50, 100, 200])
            return {"stem": f"Под нагрузкой процессу понадобилось {use}Mi памяти. Что произойдёт с контейнером?",
                    "code": code, "code_lang": "yaml",
                    "correct": "Его убьют по OOM (OOMKilled), kubelet перезапустит контейнер",
                    "distractors": ["Он замедлится (троттлинг), но продолжит работать",
                                    f"Лимит автоматически поднимется до {use}Mi",
                                    "Под перейдёт в Pending до освобождения памяти"],
                    "explanation": "Память несжимаема: превышение limits.memory приводит к OOMKill."}
        if variant == 1:
            return {"stem": "Процесс пытается загрузить 2 ядра CPU, на узле есть свободные ядра. Что произойдёт?",
                    "code": code, "code_lang": "yaml",
                    "correct": f"Процесс будет троттлиться до {lim_c}m CPU, перезапуска не будет",
                    "distractors": ["Контейнер убьют (OOMKilled) и перезапустят",
                                    "Лимит игнорируется, раз на узле есть свободные ядра",
                                    "Под вытеснят (evicted) на другой узел"],
                    "explanation": "CPU — сжимаемый ресурс: при достижении limits.cpu процесс ограничивается CFS."}
        free = rng.choice([req_c - 50, req_c // 2])
        return {"stem": f"На каждом узле кластера осталось {free}m CPU, не занятых requests других подов; "
                        f"фактическая загрузка узлов низкая. Что будет с новым подом?",
                "code": code, "code_lang": "yaml",
                "correct": "Останется в Pending: планировщик учитывает requests",
                "distractors": ["Запустится: планировщик смотрит на фактическую загрузку",
                                "Запустится, но будет троттлиться до свободных ресурсов",
                                "Запустится с уменьшенными requests"],
                "explanation": "Планировщик размещает под, только если сумма requests помещается в allocatable узла."}
    port = rng.choice([8080, 8000, 3000])
    ft = rng.choice([3, 5, 6])
    per = rng.choice([5, 10, 15])
    if variant == 3:
        code = (f"readinessProbe:\n  httpGet:\n    path: /ready\n    port: {port}\n  periodSeconds: {per}\n"
                f"  failureThreshold: {ft}")
        return {"stem": f"У пода {app} /ready начал отвечать 503 (недоступна БД). Что сделает Kubernetes?",
                "code": code, "code_lang": "yaml",
                "correct": "Исключит под из endpoints Service, перезапускать не будет",
                "distractors": [f"Перезапустит контейнер после {ft} неудачных проверок",
                                "Пересоздаст под на другом узле",
                                "Ничего: readiness проверяется только при старте"],
                "explanation": "readiness управляет приёмом трафика, liveness — перезапуском."}
    if variant == 4:
        code = (f"livenessProbe:\n  httpGet:\n    path: /healthz\n    port: {port}\n  periodSeconds: {per}\n"
                f"  failureThreshold: {ft}")
        return {"stem": f"Процесс {app} завис, /healthz перестал отвечать. Что сделает Kubernetes?",
                "code": code, "code_lang": "yaml",
                "correct": f"kubelet перезапустит контейнер после {ft} неудачных проверок подряд",
                "distractors": ["Только исключит под из endpoints Service",
                                "Deployment создаст новый под, а старый оставит",
                                "Пометит узел как NotReady"],
                "explanation": "Неудачная liveness-проба приводит к перезапуску контейнера."}
    f = rng.choice([10, 20, 30, 60])
    code = (f"startupProbe:\n  httpGet:\n    path: /healthz\n    port: {port}\n  periodSeconds: {per}\n"
            f"  failureThreshold: {f}")
    return {"stem": f"Сколько секунд максимум есть у приложения {app} на запуск, прежде чем kubelet перезапустит "
                    f"контейнер?",
            "code": code, "code_lang": "yaml",
            "correct": f"{f * per} с",
            "distractors": [f"{f} с", f"{per} с", f"{f + per} с", f"{f * per * 2} с"],
            "explanation": "startupProbe даёт failureThreshold × periodSeconds на старт; пока она не прошла, "
                           "liveness и readiness не выполняются."}


@template(id="devops.k8s_rolling_update", pool="devops", topics=["kubernetes"], fmt="calc", a=1.4, b=1.2,
          title="Kubernetes: RollingUpdate, maxSurge и maxUnavailable", variants=2000)
def _k8s_rolling_update(rng: random.Random) -> dict:
    while True:
        r = rng.randint(3, 20)
        ask = rng.choice(["max", "min"])

        def spec(force_pct):
            if force_pct or rng.random() < 0.3:
                return f"{rng.choice([10, 20, 25, 30, 40, 50])}%"
            return str(rng.randint(0, 3))

        s_spec, u_spec = spec(ask == "max"), spec(ask == "min")

        def val(sp, up):
            if sp.endswith("%"):
                x = Fraction(r * int(sp[:-1]), 100)
                return math.ceil(x) if up else math.floor(x)
            return int(sp)

        surge, unav = val(s_spec, True), val(u_spec, False)
        if surge + unav == 0:
            continue
        asked = s_spec if ask == "max" else u_spec
        if (r * int(asked[:-1])) % 100 == 0:
            continue  # проверяем округление: доля не должна делиться нацело
        s_wrong, u_wrong = val(s_spec, False), val(u_spec, True)
        if ask == "max":
            correct = r + surge
            cands = [r + s_wrong, r + surge + unav, r, r + round(r * int(s_spec[:-1]) / 100) + 1, r - unav]
        else:
            correct = r - unav
            cands = [r - u_wrong, r - unav - surge, r, r + surge, r - unav - 1]
        if len(set(cands) - {correct}) >= 3:
            break
    name = rng.choice(["orders", "gateway", "search", "notifier"])
    code = (f"kind: Deployment\nmetadata:\n  name: {name}\nspec:\n  replicas: {r}\n  strategy:\n"
            f"    type: RollingUpdate\n    rollingUpdate:\n      maxSurge: {s_spec}\n      maxUnavailable: {u_spec}")
    q = ("Какое максимальное число подов (старых и новых вместе) может существовать во время обновления?"
         if ask == "max" else "Какое минимальное число подов гарантированно останется доступным во время обновления?")
    return {
        "stem": q,
        "code": code,
        "code_lang": "yaml",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "Проценты пересчитываются от replicas: maxSurge округляется вверх, maxUnavailable — вниз. "
                       "Максимум подов = replicas + maxSurge, минимум доступных = replicas − maxUnavailable.",
    }


# ---------------------------------------------------------------------------------------------- monitoring / SRE

@template(id="devops.slo_error_budget", pool="devops", topics=["monitoring"], fmt="calc", a=1.3, b=0.4,
          title="SLO и бюджет ошибок", variants=500)
def _slo_error_budget(rng: random.Random) -> dict:
    if rng.random() < 0.5:
        while True:
            slo = rng.choice(["99", "99.5", "99.9", "99.95"])
            days = rng.choice([7, 28, 30])
            budget = Fraction(days * 1440) * (100 - Fraction(slo)) / 100
            if (budget * 10).denominator == 1:
                break
        return {
            "stem": f"SLO доступности сервиса — {slo}% за скользящее окно {days} дней. Сколько минут полной "
                    f"недоступности допускает бюджет ошибок за это окно?",
            "code": None,
            "correct": _num(budget),
            "distractors": [_num(budget * 10), _num(budget / 10), _num(budget / 60), _num(budget * 24 / 10)],
            "explanation": f"{days} × 1440 мин × (1 − {slo}%) = {_num(budget)} мин.",
        }
    while True:
        slo = rng.choice(["99", "99.5", "99.9", "99.95"])
        total = rng.randint(2, 40) * 1_000_000
        budget = Fraction(total) * (100 - Fraction(slo)) / 100
        if budget.denominator != 1:
            continue
        used = int(budget * Fraction(rng.randint(2, 8), 10))
        rem = budget - used
        cands = [budget, used, budget * 10 - used, rem * 10, rem / 10]
        if len({c for c in cands if c != rem}) >= 3 and all(Fraction(c).denominator == 1 for c in cands):
            break
    return {
        "stem": f"SLO: {slo}% успешных запросов за 30 дней. Ожидаемый трафик за окно — {total:,} запросов. "
                f"С начала окна уже было {used:,} ошибочных ответов. Сколько ошибок ещё допускает бюджет?"
                .replace(",", " "),
        "code": None,
        "correct": f"{int(rem):,}".replace(",", " "),
        "distractors": [f"{int(c):,}".replace(",", " ") for c in cands],
        "explanation": f"Бюджет = {total:,} × (1 − {slo}%) = {int(budget):,}; остаток = бюджет − израсходованное."
                       .replace(",", " "),
    }


@template(id="devops.slo_burn_rate", pool="devops", topics=["monitoring"], fmt="calc", a=1.4, b=1.6,
          title="Скорость расходования бюджета ошибок (burn rate)", variants=200)
def _slo_burn_rate(rng: random.Random) -> dict:
    variant = rng.randrange(3)
    if variant in (0, 1):
        slo, err = rng.choice([("99.9", "0.2"), ("99.9", "0.5"), ("99.9", "1"), ("99.9", "0.3"), ("99.5", "1"),
                               ("99.5", "2.5"), ("99", "2"), ("99", "5"), ("99.9", "0.6"), ("99.5", "3"),
                               ("99.95", "0.2"), ("99.95", "0.5")])
        burn = Fraction(err) / (100 - Fraction(slo))
        if variant == 0:
            return {
                "stem": f"SLO — {slo}% успешных запросов за 30 дней. Последний час доля ошибок стабильно {err}%. "
                        f"Чему равен burn rate (во сколько раз бюджет расходуется быстрее допустимого)?",
                "code": None,
                "correct": _num(burn),
                "distractors": [_num(1 / burn), _num(burn * 10), _num(Fraction(err)), _num(burn / 10)],
                "explanation": f"burn rate = доля ошибок / (1 − SLO) = {err}% / {_num(100 - Fraction(slo))}% "
                               f"= {_num(burn)}.",
            }
        hours = Fraction(720) / burn
        return {
            "stem": f"SLO — {slo}% успешных запросов за 30 дней, бюджет пока не тронут. Доля ошибок внезапно стала "
                    f"{err}% и держится. Через сколько часов бюджет за 30-дневное окно будет исчерпан полностью?",
            "code": None,
            "correct": _num(hours),
            "distractors": [_num(hours / 24), _num(hours * 2), _num(Fraction(24) / burn), _num(720 - hours)
                            if hours != 360 else _num(hours * 3)],
            "explanation": f"burn rate = {_num(burn)}, значит 30 дней (720 ч) бюджета уйдут за 720 / {_num(burn)} "
                           f"= {_num(hours)} ч.",
        }
    while True:
        b = Fraction(rng.choice(["14.4", "6", "3", "2", "1.5", "4", "12", "7.2", "36"]))
        h = rng.choice([1, 2, 3, 6, 12, 24])
        pct = b * h / 720 * 100
        if (pct * 10).denominator == 1 and pct < 100:
            break
    return {
        "stem": f"Алерт сработал: burn rate держался на уровне {_num(b)} в течение {h} ч. Какую долю бюджета "
                f"ошибок 30-дневного окна это израсходовало?",
        "code": None,
        "correct": f"{_num(pct)}%",
        "distractors": [f"{_num(pct * 24)}%" if pct * 24 < 100 else f"{_num(pct / 2)}%", f"{_num(b * h)}%",
                        f"{_num(pct / 10)}%", f"{_num(b)}%"],
        "explanation": f"Доля = burn rate × длительность / окно = {_num(b)} × {h} / 720 = {_num(pct)}%.",
    }


# ---------------------------------------------------------------------------------------------- nginx / terraform

def _nginx_resolve(locs: list[tuple[str, str]], uri: str):
    for mod, pat in locs:
        if mod == "=" and uri == pat:
            return mod, pat
    prefixes = [(mod, pat) for mod, pat in locs if mod in ("", "^~") and uri.startswith(pat)]
    best = max(prefixes, key=lambda x: len(x[1])) if prefixes else None
    if best and best[0] == "^~":
        return best
    for mod, pat in locs:
        if mod == "~" and re.search(pat, uri) or mod == "~*" and re.search(pat, uri, re.I):
            return mod, pat
    return best


def _loc_text(loc: tuple[str, str]) -> str:
    return f"location {loc[0] + ' ' if loc[0] else ''}{loc[1]}"


@template(id="devops.nginx_location", pool="devops", topics=["nginx"], fmt="calc", a=1.4, b=1.4,
          title="Выбор location в nginx", variants=3000)
def _nginx_location(rng: random.Random) -> dict:
    families = [
        (["/static/img/logo.PNG", "/static/img/icons/cart.png", "/static/css/site.css", "/static/js/app.js",
          "/media/img/photo.jpg"],
         [("", "/"), ("", "/static/"), ("^~", "/static/img/"), ("~*", r"\.(png|jpg|gif)$"), ("~", r"\.css$"),
          ("=", "/static/css/site.css"), ("", "/static/js/"), ("~", r"^/static/.+\.js$"), ("", "/media/")]),
        (["/api/v1/health", "/api/v2/users/42", "/api/v1/users/7", "/api/v10/orders", "/api/internal/metrics"],
         [("", "/"), ("", "/api/"), ("^~", "/api/v1/"), ("~", r"^/api/v[0-9]+/users"), ("=", "/api/v1/health"),
          ("", "/api/v2/users/"), ("^~", "/api/internal/"), ("~", r"/metrics$"), ("~", r"^/api/v[0-9]+/")]),
    ]
    uris, pool = rng.choice(families)
    while True:
        uri = rng.choice(uris)
        locs = [("", "/")] + rng.sample(pool[1:], 4)
        rng.shuffle(locs)
        win = _nginx_resolve(locs, uri)
        matching = [loc for loc in locs if loc[0] in ("", "^~") and uri.startswith(loc[1])
                    or loc[0] == "=" and uri == loc[1]
                    or loc[0] == "~" and re.search(loc[1], uri) or loc[0] == "~*" and re.search(loc[1], uri, re.I)]
        longest = max((loc for loc in locs if loc[0] in ("", "^~", "=") and uri.startswith(loc[1])),
                      key=lambda x: len(x[1]))
        first = matching[0]
        if len(matching) >= 3 and (win != longest or win != first):
            break
    code = "server {\n    listen 80;\n" + "\n".join(
        f"    {_loc_text(loc)} {{ return 200 \"{i}\"; }}" for i, loc in enumerate(locs, 1)) + "\n}"
    return {
        "stem": f"Какой location обработает запрос GET {uri}?",
        "code": code,
        "code_lang": "nginx",
        "correct": _loc_text(win),
        "distractors": [_loc_text(loc) for loc in [longest, first] + matching + locs if loc != win],
        "explanation": "Порядок: точное совпадение «=»; затем ищется самый длинный префикс — если у него «^~», "
                       "поиск окончен; иначе проверяются регулярные выражения (~, ~* без учёта регистра) в "
                       "порядке записи, первое совпадение побеждает; если ни одно не подошло — самый длинный "
                       "префикс.",
    }


@template(id="devops.nginx_proxy_pass", pool="devops", topics=["nginx", "http"], fmt="calc", a=1.5, b=2.0,
          title="nginx proxy_pass: преобразование URI", variants=600)
def _nginx_proxy_pass(rng: random.Random) -> dict:
    seg = rng.choice(["api", "app", "svc", "backend"])
    rest = rng.choice(["users/7", "orders/15/items", "health", "v1/search", "files/report.pdf"])
    up = rng.choice(["upstream_app", "core", "billing", "10.0.0.5:8080"])
    while True:
        loc = rng.choice([f"/{seg}/", f"/{seg}"])
        uri_part = rng.choice([None, "/", "/v2/", "/v2", "/internal/"])
        if loc == f"/{seg}" and uri_part is None:
            continue
        break
    req = f"/{seg}/{rest}"
    tail = req[len(loc):]
    correct = req if uri_part is None else uri_part + tail
    norm = re.sub("/+", "/", (uri_part or "/") + "/" + rest)
    cands = [req, norm, f"/{rest}", (uri_part or "").rstrip("/") + req, f"/{seg}{rest}", f"/{seg}//{rest}",
             re.sub("/+", "/", correct), (uri_part or "/") + seg + "/" + rest, correct + "/"]
    pp = f"http://{up}" + (uri_part or "")
    code = f"location {loc} {{\n    proxy_pass {pp};\n}}"
    return {
        "stem": f"Клиент запрашивает GET {req}. Какой URI получит upstream?",
        "code": code,
        "code_lang": "nginx",
        "correct": correct,
        "distractors": [c for c in cands if c != correct],
        "explanation": "Если в proxy_pass указан URI (даже просто «/»), часть запроса, совпавшая с префиксом "
                       "location, заменяется на этот URI буквально, без нормализации слэшей. Если URI нет — "
                       "запрос передаётся как есть.",
    }


@template(id="devops.terraform_count", pool="devops", topics=["terraform"], fmt="calc", a=1.3, b=1.3,
          title="Terraform: count и for_each при изменении списка", variants=400)
def _terraform_count(rng: random.Random) -> dict:
    pool = ["alpha", "beta", "gamma", "delta", "omega", "sigma", "kappa"]
    n = rng.randint(4, 6)
    names = rng.sample(pool, n)
    mode = rng.choice(["count", "count", "for_each"])
    while True:
        i = rng.randrange(n)
        if mode == "count" and i == n - 1 and rng.random() < 0.7:
            continue
        break
    ask = rng.choice(["destroy", "add"])
    if mode == "count":
        add, destroy = n - 1 - i, n - i
    else:
        add, destroy = 0, 1
    correct = destroy if ask == "destroy" else add
    cands = [1, 0, n - i, n - 1 - i, n - 1, n, 2 * (n - 1 - i)]
    if mode == "count":
        body = ('resource "local_file" "cfg" {\n  count    = length(var.names)\n'
                '  filename = "${var.names[count.index]}.conf"\n  content  = "managed"\n}')
    else:
        body = ('resource "local_file" "cfg" {\n  for_each = toset(var.names)\n'
                '  filename = "${each.key}.conf"\n  content  = "managed"\n}')
    lst = ", ".join(f'"{x}"' for x in names)
    code = f'variable "names" {{\n  default = [{lst}]\n}}\n\n{body}'
    word = "to destroy" if ask == "destroy" else "to add"
    return {
        "stem": f"Ресурсы созданы по этой конфигурации. Затем из списка удалили \"{names[i]}\" и выполнили "
                f"terraform plan. Какое число будет в итоге плана в поле «{word}»? (Любое изменение атрибутов "
                f"local_file требует пересоздания ресурса.)",
        "code": code,
        "code_lang": "hcl",
        "correct": str(correct),
        "distractors": [str(c) for c in cands if c != correct],
        "explanation": "С count ресурсы адресуются индексом: после удаления элемента все последующие индексы "
                       "получают другие значения и пересоздаются (replace = add + destroy), последний индекс "
                       "удаляется. С for_each ключом служит само значение — удаляется ровно один ресурс.",
    }
