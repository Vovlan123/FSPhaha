"""Пул шаблонов специализации «data». Каждый шаблон регистрируется декоратором @template (см. base.py).

pandas/torch/sklearn в окружении нет: ответы считаются в генераторах обычным Python по документированной семантике
(skipna=True по умолчанию в pandas, правила broadcasting NumPy, формула размера выхода свёртки и т. д.).
"""
import math
import random
import statistics
from itertools import zip_longest

from app.services.bank.base import template


def _n(x: float) -> str:
    """Число без лишнего хвоста: 12 вместо 12.0, 12.5 как есть."""
    return str(int(x)) if float(x).is_integer() else str(x)


def _f2(x: float) -> str:
    return f"{x:.2f}"


def _near_half(x: float, digits: int = 2) -> bool:
    """Значение на границе округления — такие экземпляры пропускаем, чтобы ключ не зависел от способа округления."""
    v = abs(x) * 10 ** digits
    return abs(v - math.floor(v) - 0.5) < 1e-6


def _qlist(xs: list) -> str:
    return "[" + ", ".join(f'"{x}"' for x in xs) + "]"


# --- Статистика: среднее и медиана --------------------------------------------------------------------
@template(id="data.mean_median", pool="data", topics=["statistics"], fmt="calc", a=1.0, b=-1.5,
          title="Среднее и медиана", variants=2000)
def _mean_median(rng: random.Random) -> dict:
    kind = rng.randrange(3)
    for _ in range(300):
        n = 7 if kind == 0 else 6 if kind == 1 else rng.choice([5, 6])
        xs = rng.sample(range(10, 60), n - 1) + [rng.randint(150, 400)]  # один выброс
        if kind == 2:
            xs[-1] += (-sum(xs)) % n  # среднее — целое
        rng.shuffle(xs)
        s = sorted(xs)
        mean = sum(xs) / n
        if kind == 0:
            correct = _n(s[n // 2])
            cands = [_n(round(mean, 1)), _n(xs[n // 2]), _n(s[n // 2 - 1]), _n(s[n // 2 + 1])]
            what = "медиана"
        elif kind == 1:
            correct = _n((s[2] + s[3]) / 2)
            cands = [_n(s[2]), _n(s[3]), _n(round(mean, 1)), _n((xs[2] + xs[3]) / 2)]
            what = "медиана"
        else:
            correct = _n(mean)
            cands = [_n(statistics.median(xs)), _n(round(sum(xs) / (n - 1), 1)), _n(round((sum(xs) - s[-1]) / (n - 1), 1))]
            what = "среднее арифметическое"
        if len(set(cands) - {correct}) >= 3:
            break
    return {
        "stem": f"Время ответа сервиса (мс) в {n} запросах: {xs}. Чему равно {what}?" if what != "медиана" else
                f"Время ответа сервиса (мс) в {n} запросах: {xs}. Чему равна медиана?",
        "correct": correct,
        "distractors": cands,
        "explanation": "Медиана — середина отсортированного ряда (при чётном n — среднее двух центральных), она устойчива "
                       "к выбросам; среднее арифметическое выброс сильно сдвигает.",
    }


# --- pandas: булева фильтрация ----------------------------------------------------------------------
@template(id="data.pandas_filter", pool="data", topics=["pandas"], fmt="output", a=1.1, b=-1.2,
          title="Фильтрация DataFrame", variants=2000)
def _pandas_filter(rng: random.Random) -> dict:
    cities = rng.sample(["Kazan", "Omsk", "Perm", "Tula", "Sochi"], 3)
    x, y = cities[0], cities[1]
    for _ in range(300):
        rows = [(rng.choice(cities), rng.choice(range(20, 301, 10))) for _ in range(6)]
        kind = rng.randrange(3)
        if kind == 0:
            in_x = [s for c, s in rows if c == x]
            if not in_x:
                continue
            p = rng.choice(in_x)
            expr = f'(df["city"] == "{x}") & (df["sales"] > {p})'
            correct = sum(c == x and s > p for c, s in rows)
            cands = [sum(c == x and s >= p for c, s in rows), sum(c == x or s > p for c, s in rows),
                     sum(c == x for c, s in rows), sum(s > p for c, s in rows)]
        elif kind == 1:
            p = rng.choice([s for _, s in rows])
            expr = f'(df["city"] == "{x}") | (df["sales"] >= {p})'
            correct = sum(c == x or s >= p for c, s in rows)
            cands = [sum(c == x and s >= p for c, s in rows), sum(c == x or s > p for c, s in rows),
                     sum(c == x for c, s in rows), sum(s >= p for c, s in rows)]
        else:
            p = rng.choice([s for _, s in rows])
            expr = f'df["city"].isin(["{x}", "{y}"]) & ~(df["sales"] > {p})'
            correct = sum(c in (x, y) and s <= p for c, s in rows)
            cands = [sum(c in (x, y) and s > p for c, s in rows), sum(c in (x, y) for c, s in rows),
                     sum(s <= p for c, s in rows), sum(c in (x, y) and s < p for c, s in rows)]
        if len(set(cands) - {correct}) >= 3:
            break
    code = (f"import pandas as pd\n\ndf = pd.DataFrame({{\n    \"city\": {_qlist([c for c, _ in rows])},\n"
            f"    \"sales\": {[s for _, s in rows]},\n}})\nprint(len(df[{expr}]))")
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "& — поэлементное И, | — ИЛИ, ~ — отрицание; каждое условие берётся в скобки. isin проверяет "
                       "принадлежность списку.",
    }


# --- ML: диагностика переобучения ---------------------------------------------------------------------
@template(id="data.fit_diagnosis", pool="data", topics=["ml"], fmt="concept", a=1.0, b=-0.8,
          title="Переобучение и недообучение", variants=500)
def _fit_diagnosis(rng: random.Random) -> dict:
    model = rng.choice(["случайный лес", "градиентный бустинг", "нейросеть", "дерево решений"])
    metric = rng.choice(["accuracy", "ROC-AUC", "F1"])
    over = "Переобучение: усилить регуляризацию, упростить модель, добавить данные"
    under = "Недообучение: усложнить модель или добавить информативные признаки"
    kind = rng.randrange(4)
    if kind == 0:
        tr, va = rng.randint(97, 100) / 100, rng.randint(62, 78) / 100
        stem = f"Модель «{model}»: {metric} на обучении {tr:.2f}, на валидации {va:.2f}. Что происходит и что делать?"
        correct, d = over, [under, "Всё в порядке: разрыв между выборками нормален",
                            "Ошибка в метрике: на обучении она не может быть выше"]
    elif kind == 1:
        tr = rng.randint(58, 66) / 100
        va = tr - rng.randint(0, 3) / 100
        stem = (f"Модель «{model}»: {metric} на обучении {tr:.2f}, на валидации {va:.2f}; у сильных решений задачи "
                f"около 0.90. Что происходит и что делать?")
        correct, d = under, [over, "Всё в порядке: метрики близки, модель идеальна",
                             "Собрать больше данных того же вида — этого достаточно"]
    elif kind == 2:
        d1, d2 = rng.choice([(3, 20), (4, 30), (2, 25), (5, 40)])
        stem = (f"У дерева решений увеличили max_depth с {d1} до {d2}: {metric} на обучении вырос до 1.00, "
                f"на валидации упал. Как это объяснить?")
        correct = "Выросла дисперсия: модель запоминает шум обучающей выборки"
        d = ["Выросло смещение: модель стала слишком простой", "Валидационная выборка испорчена",
             "Глубина не влияет на качество, это случайность"]
    else:
        stem = (f"Кривые обучения модели «{model}»: с ростом объёма данных ошибка на обучении и на валидации "
                f"сходятся к одному высокому значению. Поможет ли сбор ещё большего числа данных?")
        correct = "Почти нет: это высокое смещение, нужна более сложная модель"
        d = ["Да: данных всегда не хватает", "Да: это признак переобучения", "Нет: нужно усилить регуляризацию"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "Большой разрыв train/validation — высокая дисперсия (переобучение); обе метрики низкие и близки — "
                       "высокое смещение (недообучение), которое не лечится ни данными, ни регуляризацией.",
    }


# --- pandas: groupby ---------------------------------------------------------------------------------
@template(id="data.pandas_groupby", pool="data", topics=["pandas"], fmt="output", a=1.2, b=-0.6,
          title="Агрегация groupby в pandas", variants=2000)
def _pandas_groupby(rng: random.Random) -> dict:
    teams = rng.sample(["red", "blue", "green", "black", "white"], 3)
    agg = rng.choice(["sum", "mean", "max", "min", "count"])

    def calc(vals: list, how: str) -> str:
        if how == "sum":
            return str(sum(vals))
        if how == "mean":
            return str(sum(vals) / len(vals))  # float64 печатается как обычный float: 12.0 / 12.5
        if how == "max":
            return str(max(vals))
        if how == "min":
            return str(min(vals))
        return str(len(vals))

    for _ in range(500):
        rows = [(rng.choice(teams), rng.randint(1, 30)) for _ in range(7)]
        t = rng.choice(teams)
        vals = [s for tm, s in rows if tm == t]
        if len(vals) < 2 or len(set(vals)) < 2:
            continue
        if (sum(vals) * 2) % len(vals):  # среднее должно быть x.0 или x.5
            continue
        others = [tm for tm, _ in rows if tm != t]
        other = others[0] if others else t
        correct = calc(vals, agg)
        cands = [calc(vals, h) for h in ("sum", "mean", "max", "min", "count") if h != agg]
        cands += [calc([s for _, s in rows], agg), calc([s for tm, s in rows if tm == other], agg)]
        if len(set(cands) - {correct}) >= 3:
            break
    code = (f"import pandas as pd\n\ndf = pd.DataFrame({{\n    \"team\": {_qlist([tm for tm, _ in rows])},\n"
            f"    \"score\": {[s for _, s in rows]},\n}})\nres = df.groupby(\"team\")[\"score\"].{agg}()\n"
            f"print(res[\"{t}\"])")
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": correct,
        "distractors": cands,
        "explanation": f"groupby собирает строки по значению team, затем {agg}() считается отдельно для каждой группы; "
                       f"res — Series с индексом из названий команд.",
    }


# --- Метрики классификации ------------------------------------------------------------------------------
_METRIC_NAMES = {"precision": "точность (precision)", "recall": "полнота (recall)", "f1": "F1-мера",
                 "accuracy": "доля верных ответов (accuracy)"}


@template(id="data.precision_recall", pool="data", topics=["ml"], fmt="calc", a=1.3, b=-0.4,
          title="Метрики классификации: precision, recall, F1", variants=2000)
def _precision_recall(rng: random.Random) -> dict:
    metric = rng.choice(list(_METRIC_NAMES))
    for _ in range(500):
        tp, fn, fp, tn = rng.randint(20, 90), rng.randint(5, 40), rng.randint(5, 40), rng.randint(50, 300)
        p, r = tp / (tp + fp), tp / (tp + fn)
        vals = {"precision": p, "recall": r, "f1": 2 * p * r / (p + r), "accuracy": (tp + tn) / (tp + fn + fp + tn)}
        if any(_near_half(v) for v in vals.values()):
            continue
        correct = _f2(vals[metric])
        cands = [_f2(v) for k, v in vals.items() if k != metric] + [_f2((p + r) / 2), _f2(tp / (tp + fp + fn))]
        if len(set(cands) - {correct}) >= 3:
            break
    code = (f"                предсказано 1   предсказано 0\nфакт 1          TP = {tp:<10}  FN = {fn}\n"
            f"факт 0          FP = {fp:<10}  TN = {tn}")
    return {
        "stem": f"Матрица ошибок бинарного классификатора приведена ниже. Чему равна {_METRIC_NAMES[metric]}? "
                f"Округлите до сотых.",
        "code": code,
        "code_lang": "text",
        "correct": correct,
        "distractors": cands,
        "explanation": "precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2·P·R/(P+R) — гармоническое, а не "
                       "арифметическое среднее; accuracy = (TP+TN)/всего.",
    }


# --- Несбалансированные классы ----------------------------------------------------------------------------
@template(id="data.class_imbalance", pool="data", topics=["ml"], fmt="calc", a=1.2, b=-0.2,
          title="Метрики при несбалансированных классах", variants=500)
def _class_imbalance(rng: random.Random) -> dict:
    kind = rng.randrange(3)
    for _ in range(500):
        n = rng.choice([1000, 2000, 5000, 10000])
        rate = rng.choice([0.5, 1, 2, 4, 5])
        pos = int(n * rate / 100)
        if kind == 0:
            acc = (n - pos) / n * 100
            stem = (f"В выборке {n} транзакций, из них {pos} мошеннических. Модель всегда предсказывает "
                    f"«не мошенничество». Чему равна её accuracy?")
            correct = f"{acc:.1f}%"
            cands = [f"{rate:.1f}%", "50.0%", "0.0%", f"{100 - 2 * rate:.1f}%"]
            break
        k = rng.randint(pos // 2, pos * 2)
        m = rng.randint(max(1, pos // 4), min(k, pos) - 1)
        prec, rec = m / k, m / pos
        acc = (m + (n - pos - (k - m))) / n
        vals = [prec, rec, acc, m / n]
        if any(_near_half(v) for v in vals):
            continue
        stem = (f"В выборке {n} транзакций, из них {pos} мошеннических. Модель пометила {k} транзакций как "
                f"мошеннические, из них {m} действительно мошеннические. Чему равна её "
                f"{'полнота (recall)' if kind == 1 else 'точность (precision)'}? Округлите до сотых.")
        correct = _f2(rec if kind == 1 else prec)
        cands = [_f2(prec if kind == 1 else rec), _f2(acc), _f2(m / n), _f2(k / n)]
        if len(set(cands) - {correct}) >= 3:
            break
    return {
        "stem": stem,
        "correct": correct,
        "distractors": cands,
        "explanation": "При редком положительном классе accuracy почти не информативна: константная модель получает "
                       "высокий балл. Полнота = найденные / все положительные, точность = верные / все помеченные.",
    }


# --- SQL: агрегаты и NULL ----------------------------------------------------------------------------
@template(id="data.sql_avg_null", pool="data", topics=["sql"], fmt="calc", a=1.2, b=0.2,
          title="AVG, COALESCE и NULL в SQL", variants=2000)
def _sql_avg_null(rng: random.Random) -> dict:
    users = rng.sample(["anna", "boris", "vera", "gleb", "dina", "egor", "ilya", "kira"], 7)
    kind = rng.randrange(4)
    for _ in range(300):
        n = rng.choice([6, 7])
        scores = [rng.randint(1, 5) for _ in range(n)]
        for i in rng.sample(range(n), rng.randint(1, 3)):
            scores[i] = None
        vals = [v for v in scores if v is not None]
        nn, sm = len(vals), sum(vals)
        if kind == 0:
            q = "SELECT AVG(score)\nFROM ratings;"
            correct, cands = _f2(sm / nn), [_f2(sm / n), "NULL", _f2(sm / (nn + 1)), _f2(sm / (nn - 1))]
        elif kind == 1:
            q = "SELECT AVG(COALESCE(score, 0))\nFROM ratings;"
            correct, cands = _f2(sm / n), [_f2(sm / nn), "NULL", _f2(sm / (n - 1)), _f2(sm / (n + 1))]
        elif kind == 2:
            q = "SELECT SUM(score) * 1.0 / COUNT(*)\nFROM ratings;"
            correct, cands = _f2(sm / n), [_f2(sm / nn), "NULL", _f2(sm / (n - 1)), _f2(sm / (n + 1))]
        else:
            q = "SELECT COUNT(*)\nFROM ratings\nWHERE score < 3 OR score >= 3;"
            correct, cands = str(nn), [str(n), str(n - nn), str(nn - 1), str(nn + 1)]
        if nn >= 2 and len(set(cands) - {correct}) >= 3 and not any(
                _near_half(x) for x in (sm / n, sm / nn, sm / (n - 1), sm / (n + 1), sm / (nn + 1), sm / (nn - 1))):
            break
    rows = "\n".join(f"-- {u:<5} | {'NULL' if v is None else v}" for u, v in zip(users, scores))
    return {
        "stem": "Что вернёт запрос? Дробный результат округлите до сотых.",
        "code": f"-- ratings\n-- user_name | score\n{rows}\n{q}",
        "code_lang": "sql",
        "correct": correct,
        "distractors": cands,
        "explanation": "AVG и SUM пропускают NULL, поэтому AVG(score) делит только на число непустых значений. "
                       "COALESCE превращает NULL в 0, и делитель становится равен числу строк. Сравнение с NULL "
                       "даёт UNKNOWN, такие строки не проходят WHERE.",
    }


# --- NumPy: broadcasting --------------------------------------------------------------------------------
def _bcast(a: tuple, b: tuple, right: bool = True):
    xs, ys = (reversed(a), reversed(b)) if right else (a, b)
    out = []
    for x, y in zip_longest(xs, ys, fillvalue=1):
        if x != y and x != 1 and y != 1:
            return None
        out.append(max(x, y))
    return tuple(reversed(out)) if right else tuple(out)


_BERR = "Ошибка ValueError: формы несовместимы"


@template(id="data.numpy_broadcast", pool="data", topics=["numpy"], fmt="calc", a=1.3, b=0.3,
          title="Broadcasting в NumPy", variants=1000)
def _numpy_broadcast(rng: random.Random) -> dict:
    want_error = rng.random() < 0.25  # доля экземпляров с ответом «ошибка» близка к 1/4
    for _ in range(1000):
        target = tuple(rng.sample([2, 3, 4, 5, 6], rng.randint(2, 3)))
        a = tuple(1 if rng.random() < 0.35 else d for d in target[-rng.randint(1, len(target)):])
        b = tuple(1 if rng.random() < 0.35 else d for d in target[-rng.randint(1, len(target)):])
        if want_error:  # ломаем совместимость
            i = rng.randrange(len(b))
            b = b[:i] + (rng.choice([2, 3, 4, 5, 6, 7]),) + b[i + 1:]
        res = _bcast(a, b)
        if a == b or (res is None) != want_error:
            continue
        correct = str(res) if res else _BERR
        left = _bcast(a, b, right=False)
        naive = tuple(max(x, y) for x, y in zip_longest(reversed(a), reversed(b), fillvalue=1))[::-1]
        cands = [str(left) if left else _BERR, str(a), str(b), str(naive), _BERR if res else str(a + b)]
        if len(set(cands) - {correct}) >= 3 and (res is None or max(res) > 1):
            break
    op = rng.choice(["+", "*", "-"])
    code = f"import numpy as np\n\na = np.ones({a})\nb = np.ones({b})\nprint((a {op} b).shape)"
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": correct,
        "distractors": cands,
        "explanation": "Формы выравниваются по правому краю; в каждой позиции размеры должны совпадать или один из них "
                       "равен 1 (недостающие измерения считаются равными 1). Иначе — ValueError.",
    }


# --- pandas/NumPy: NaN ---------------------------------------------------------------------------------
@template(id="data.nan_semantics", pool="data", topics=["pandas", "numpy"], fmt="calc", a=1.3, b=0.5,
          title="Пропуски (NaN) в pandas и NumPy", variants=2000)
def _nan_semantics(rng: random.Random) -> dict:
    kind = rng.randrange(4)
    for _ in range(500):
        n = rng.choice([4, 5, 6])
        vals = [float(rng.randint(1, 12)) for _ in range(n)]
        nan_idx = rng.sample(range(n), rng.randint(1, 2))
        present = [v for i, v in enumerate(vals) if i not in nan_idx]
        mean, mean0, total = sum(present) / len(present), sum(present) / n, sum(present)
        if any(round(x, 2) != x for x in (mean, mean0)):
            continue
        shown = ", ".join("np.nan" if i in nan_idx else str(v) for i, v in enumerate(vals))
        cnt, k = len(present), len(nan_idx)
        if kind == 0:
            setup, ask = f"s = pd.Series([{shown}])", "s.mean() и s.count()"
            correct = f"{mean} и {cnt}"
            cands = [f"nan и {cnt}", f"{mean0} и {n}", f"{mean} и {n}", f"nan и {n}"]
        elif kind == 1:
            setup, ask = f"arr = np.array([{shown}])", "np.mean(arr) и np.nanmean(arr)"
            correct = f"nan и {mean}"
            cands = [f"{mean} и {mean}", f"{mean0} и {mean}", "nan и nan", f"{mean} и nan"]
        elif kind == 2:
            setup, ask = f"s = pd.Series([{shown}])", "s.fillna(0).mean() и s.mean()"
            correct = f"{mean0} и {mean}"
            cands = [f"{mean} и {mean}", f"{mean0} и nan", f"{mean} и {mean0}", f"{mean0} и {mean0}"]
        else:
            setup, ask = f"s = pd.Series([{shown}])", "s.sum() и s.isna().sum()"
            correct = f"{total} и {k}"
            cands = [f"nan и {k}", f"{total} и {n}", f"{total} и {cnt}", f"nan и {cnt}"]
        if len(set(cands) - {correct}) >= 3:
            break
    code = f"import numpy as np\nimport pandas as pd\n\n{setup}"
    return {
        "stem": f"Чему равны {ask}?",
        "code": code,
        "code_lang": "python",
        "correct": correct,
        "distractors": cands,
        "explanation": "Методы pandas по умолчанию пропускают NaN (skipna=True), count() считает только непустые. "
                       "np.mean распространяет NaN, np.nanmean его игнорирует; fillna(0) добавляет нули в знаменатель.",
    }


# --- Статистика: интерпретация p-value и интервалов --------------------------------------------------
@template(id="data.pvalue", pool="data", topics=["statistics", "ab_testing"], fmt="concept", a=1.2, b=0.5,
          title="Интерпретация p-value", variants=150)
def _pvalue(rng: random.Random) -> dict:
    metric = rng.choice(["конверсии в покупку", "среднего чека", "доли повторных заказов", "CTR баннера"])
    kind = rng.randrange(4)
    if kind == 0:
        p = rng.choice([0.003, 0.01, 0.02, 0.04])
        stem = f"A/B-тест {metric}: p-value = {p}. Что это означает?"
        correct = "Вероятность получить такое или более сильное различие, если H0 верна"
        d = [f"Вероятность того, что H0 верна, равна {p}", f"Вероятность того, что B лучше A, равна {1 - p:.3g}",
             f"С вероятностью {1 - p:.3g} эффект воспроизведётся"]
    elif kind == 1:
        p = rng.choice([0.12, 0.21, 0.34, 0.47])
        stem = f"A/B-тест {metric}: p-value = {p} при α = 0.05. Какой вывод корректен?"
        correct = "Нет оснований отвергнуть H0; это не доказывает отсутствие эффекта"
        d = ["Доказано, что эффекта нет", f"Эффект есть с вероятностью {1 - p:.2f}",
             "Нужно повысить α до 0.2 и признать эффект значимым"]
    elif kind == 2:
        n = rng.choice([2, 5, 10])
        eff = rng.choice([0.01, 0.02, 0.03])
        stem = (f"Тест {metric} на {n} млн пользователей в группе: прирост +{eff}% (относительно), p-value < 0.001. "
                f"Как это понимать?")
        correct = "Различие статистически значимо, но может быть практически неважным"
        d = ["Раз p так мал, эффект большой", "Результат точно повторится в любом следующем тесте",
             "Тест некорректен: p-value не бывает таким маленьким"]
    else:
        lo = rng.choice([-1.2, -0.8, -0.4, 0.2, 0.5, 0.9])
        hi = round(lo + rng.choice([0.6, 1.0, 1.4, 1.8]), 1)
        stem = f"95% доверительный интервал для разницы {metric} (B − A, п. п.): [{lo}; {hi}]. Какой вывод верен?"
        if lo < 0 < hi:
            correct = "Различие незначимо на уровне 5%: интервал содержит 0"
            d = ["B значимо лучше A: верхняя граница больше 0", "A значимо лучше B: нижняя граница меньше 0",
                 f"С вероятностью 95% разница равна {round((lo + hi) / 2, 2)} п. п."]
        elif hi < 0:
            correct = "A значимо лучше B на уровне 5%: интервал целиком меньше 0"
            d = ["Различие незначимо: интервал слишком широкий", "B значимо лучше A",
                 f"С вероятностью 95% разница равна {round((lo + hi) / 2, 2)} п. п."]
        else:
            correct = "B значимо лучше A на уровне 5%: интервал не содержит 0"
            d = ["Различие незначимо: интервал слишком широкий", "A значимо лучше B",
                 f"С вероятностью 95% разница равна {round((lo + hi) / 2, 2)} п. п."]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "p-value — вероятность наблюдать такое или более экстремальное различие при верной H0; это не "
                       "вероятность гипотез. Незначимость ≠ отсутствие эффекта, значимость ≠ практическая важность. "
                       "95% ДИ, не содержащий 0, соответствует значимости на уровне 5%.",
    }


# --- Свёрточные сети: размер выхода ------------------------------------------------------------------
@template(id="data.conv_output", pool="data", topics=["deep_learning", "pytorch"], fmt="output", a=1.2, b=0.6,
          title="Размерности в свёрточной сети", variants=2000)
def _conv_output(rng: random.Random) -> dict:
    for _ in range(500):
        bs, cin, cout = rng.choice([1, 8, 16, 32]), rng.choice([1, 3]), rng.choice([8, 16, 32, 64])
        h, k, s, p = rng.choice([28, 32, 64, 96, 128]), rng.choice([3, 5, 7]), rng.choice([1, 2]), rng.choice([0, 1, 2])
        pool = rng.random() < 0.4
        ho = (h + 2 * p - k) // s + 1
        variants_ = [(h - k) // s + 1, h + 2 * p - k + 1, math.ceil((h + 2 * p - k) / s) + 1, h // s]
        if pool:
            ho, variants_ = ho // 2, [v // 2 for v in variants_] + [(h + 2 * p - k) // s + 1]

        def shp(c: int, x: int) -> str:
            return f"torch.Size([{bs}, {c}, {x}, {x}])"

        correct = shp(cout, ho)
        cands = [shp(cout, v) for v in variants_] + [shp(cin, ho)]
        if len(set(cands) - {correct}) >= 3:
            break
    lines = ["import torch", "from torch import nn", "", f"x = torch.randn({bs}, {cin}, {h}, {h})",
             f"conv = nn.Conv2d({cin}, {cout}, kernel_size={k}, stride={s}, padding={p})", "y = conv(x)"]
    if pool:
        lines.append("y = nn.MaxPool2d(2)(y)")
    lines.append("print(y.shape)")
    return {
        "stem": "Что выведет этот код?",
        "code": "\n".join(lines),
        "code_lang": "python",
        "correct": correct,
        "distractors": cands,
        "explanation": "H_out = ⌊(H + 2·padding − kernel) / stride⌋ + 1, число каналов = out_channels; "
                       "MaxPool2d(2) делит размер на 2 с округлением вниз.",
    }


# --- pandas: merge и число строк -------------------------------------------------------------------
def _merge_count(lk: list, rk: list, how: str) -> int:
    inner = sum(lk.count(k) * rk.count(k) for k in set(lk))
    only_l = sum(1 for k in lk if k not in rk)
    only_r = sum(1 for k in rk if k not in lk)
    return {"inner": inner, "left": inner + only_l, "right": inner + only_r, "outer": inner + only_l + only_r}[how]


@template(id="data.pandas_merge", pool="data", topics=["pandas"], fmt="output", a=1.4, b=0.7,
          title="Соединение таблиц merge в pandas", variants=2000)
def _pandas_merge(rng: random.Random) -> dict:
    for _ in range(500):
        lk = sorted(rng.choice([1, 1, 2, 2, 3, 4, 5]) for _ in range(rng.randint(4, 5)))
        rk = sorted(rng.choice([1, 2, 2, 3, 5, 6]) for _ in range(rng.randint(3, 5)))
        how = rng.choice(["inner", "left", "right", "outer"])
        correct = _merge_count(lk, rk, how)
        cands = [_merge_count(lk, rk, h) for h in ("inner", "left", "right", "outer") if h != how]
        cands += [len(lk), len(rk), len(set(lk) & set(rk))]
        if correct not in (len(lk), len(rk)) and len(set(cands) - {correct}) >= 3:
            break
    amounts = rng.sample(range(10, 100, 5), len(lk))
    segs = rng.sample(["a", "b", "c", "d", "e", "f"], len(rk))
    code = (f"import pandas as pd\n\nleft = pd.DataFrame({{\"user_id\": {lk}, \"amount\": {amounts}}})\n"
            f"right = pd.DataFrame({{\"user_id\": {rk}, \"segment\": {_qlist(segs)}}})\n"
            f"m = left.merge(right, on=\"user_id\", how=\"{how}\")\nprint(len(m))")
    return {
        "stem": "Что выведет этот код?",
        "code": code,
        "code_lang": "python",
        "correct": str(correct),
        "distractors": [str(c) for c in cands],
        "explanation": "Каждая пара строк с одинаковым ключом даёт строку результата (дубликаты ключей размножают "
                       "строки). left/right/outer добавляют по одной строке на ключ без пары с соответствующей стороны.",
    }


# --- ML: регуляризация --------------------------------------------------------------------------------
@template(id="data.regularization", pool="data", topics=["ml", "scikit_learn"], fmt="concept", a=1.1, b=1.0,
          title="Регуляризация и bias-variance", variants=30)
def _regularization(rng: random.Random) -> dict:
    a1 = rng.choice([0.01, 0.1, 0.5])
    a2 = a1 * rng.choice([10, 100])
    kind = rng.randrange(5)
    if kind == 0:
        stem = f"В Lasso (L1) увеличили alpha с {a1} до {a2:g}. Что произойдёт с коэффициентами?"
        correct = "Больше коэффициентов станут ровно нулевыми"
        d = ["Коэффициенты уменьшатся, но ни один не станет нулём", "Все коэффициенты вырастут по модулю",
             "Ничего: alpha влияет только на скорость сходимости"]
    elif kind == 1:
        stem = f"В Ridge (L2) увеличили alpha с {a1} до {a2:g}. Что произойдёт с коэффициентами?"
        correct = "Сожмутся к нулю, но, как правило, не обнулятся"
        d = ["Часть коэффициентов станет ровно нулём", "Все коэффициенты вырастут по модулю",
             "Ничего: alpha влияет только на скорость сходимости"]
    elif kind == 2:
        c1 = rng.choice([1.0, 10.0, 100.0])
        stem = f"В LogisticRegression из scikit-learn параметр C уменьшили с {c1:g} до {c1 / 100:g}. Что изменилось?"
        correct = "Регуляризация усилилась: модель проще, смещение выше"
        d = ["Регуляризация ослабла: модель сложнее", "Уменьшилась скорость обучения (learning rate)",
             "Ничего: C влияет только на число итераций"]
    elif kind == 3:
        stem = f"Регуляризацию модели усилили (alpha: {a1} → {a2:g}). Как обычно меняются смещение и дисперсия?"
        correct = "Смещение растёт, дисперсия падает"
        d = ["Смещение падает, дисперсия растёт", "Оба растут", "Оба падают"]
    else:
        f1, f2 = rng.choice([("возраст в годах", "доход в рублях"), ("площадь в м²", "цена в рублях"),
                             ("число визитов", "выручка в рублях")])
        stem = (f"Ridge обучают на сырых признаках «{f1}» и «{f2}» без масштабирования (alpha = {a1}). "
                f"В чём проблема?")
        correct = "Штраф действует неравномерно: признаки нужно стандартизовать"
        d = ["Проблемы нет: L2-штраф не зависит от масштаба признаков", "Ridge не работает с числовыми признаками",
             "Нужно убрать регуляризацию, тогда масштаб будет важен"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "L1 обнуляет часть коэффициентов (отбор признаков), L2 равномерно сжимает их. В scikit-learn "
                       "C = 1/λ: меньше C — сильнее регуляризация. Сильнее регуляризация — выше смещение, ниже "
                       "дисперсия. Штраф зависит от масштаба коэффициентов, поэтому признаки стандартизуют.",
    }


# --- Статистика: множественные сравнения -------------------------------------------------------------
@template(id="data.multiple_comparisons", pool="data", topics=["statistics", "ab_testing"], fmt="calc", a=1.3, b=1.1,
          title="Множественные сравнения", variants=40)
def _multiple_comparisons(rng: random.Random) -> dict:
    kind = rng.randrange(3)
    for _ in range(200):
        alpha = rng.choice([0.05, 0.01, 0.1])
        m = rng.choice([5, 10, 20, 25, 50])
        fwer = 1 - (1 - alpha) ** m
        if kind == 0:
            if _near_half(fwer):
                continue
            stem = (f"В A/A-тесте (эффекта нет) независимо проверяют {m} метрик, каждую на уровне α = {alpha}. "
                    f"Какова вероятность хотя бы одного ложного «значимого» результата? Округлите до сотых.")
            correct = _f2(fwer)
            cands = [_f2(min(alpha * m, 1)), _f2(alpha), _f2((1 - alpha) ** m), _f2(alpha ** m)]
        elif kind == 1:
            stem = (f"Проверяют {m} гипотез, общий уровень (FWER) нужно удержать на {alpha}. Какой порог p-value для "
                    f"каждой гипотезы даёт поправка Бонферрони?")
            correct = f"{alpha / m:g}"
            cands = [f"{alpha:g}", f"{min(alpha * m, 1):g}", f"{alpha / 2:g}", f"{alpha / (m - 1):.4g}"]
        else:
            stem = (f"В A/A-тесте (эффекта нет) проверяют {m} независимых метрик на уровне α = {alpha}. Сколько "
                    f"ложных «значимых» результатов получится в среднем?")
            correct = f"{alpha * m:g}"
            cands = ["0", _f2(fwer), f"{m * (1 - alpha):g}", f"{alpha:g}"]
        if len(set(cands) - {correct}) >= 3:
            break
    return {
        "stem": stem,
        "correct": correct,
        "distractors": cands,
        "explanation": "P(хотя бы одна ошибка I рода) = 1 − (1 − α)^m; ожидаемое число ложных срабатываний = m·α; "
                       "Бонферрони проверяет каждую гипотезу на уровне α/m.",
    }


# --- ML: утечки в валидации --------------------------------------------------------------------------
@template(id="data.cv_leakage", pool="data", topics=["ml", "scikit_learn"], fmt="concept", a=1.3, b=1.3,
          title="Утечки данных при валидации", variants=60)
def _cv_leakage(rng: random.Random) -> dict:
    n = rng.choice(["20 000", "150 000", "1,2 млн"])
    folds = rng.choice([3, 5, 10])
    k = rng.choice([20, 50, 100])
    kind = rng.randrange(6)
    if kind == 0:
        stem = (f"Из 5000 признаков на всём датасете ({n} строк) отобрали {k} самых коррелирующих с таргетом, затем "
                f"оценили модель {folds}-fold кросс-валидацией. Что не так?")
        correct = "Отбор признаков видел таргет валидационных фолдов: оценка завышена"
        d = ["Ничего: отбор признаков не обучает модель", "Нужно больше фолдов, иначе оценка занижена",
             f"Ошибка только в том, что {k} признаков слишком мало"]
    elif kind == 1:
        stem = (f"Прогноз продаж по дням (данные за 3 года, {n} строк) оценивают KFold(n_splits={folds}, "
                f"shuffle=True). Что не так?")
        correct = "Будущее попадает в обучение: нужна TimeSeriesSplit (валидация после train)"
        d = ["Ничего: перемешивание уменьшает дисперсию оценки", "Нужен StratifiedKFold по таргету",
             "Нужно увеличить число фолдов"]
    elif kind == 2:
        stem = (f"В датасете ({n} строк) у каждого пользователя в среднем 15 записей. Модель оценивают обычным "
                f"KFold по строкам. Что не так?")
        correct = "Записи одного пользователя в train и val: нужен GroupKFold по user_id"
        d = ["Ничего: KFold подходит для любых табличных данных", "Нужен StratifiedKFold по таргету",
             "Нужно удалить пользователей с одной записью"]
    elif kind == 3:
        stem = (f"Классы 1:{k}. Сначала сделали оверсэмплинг (SMOTE) на всём датасете, затем {folds}-fold "
                f"кросс-валидацию. Что не так?")
        correct = "Синтетика из валидационных объектов попала в train: SMOTE — внутри фолда"
        d = ["Ничего: SMOTE не использует таргет", "SMOTE нужно применять только к тесту",
             "Ошибка в том, что нужно было делать андерсэмплинг"]
    elif kind == 4:
        stem = (f"Категорию «город» закодировали средним таргетом (target encoding) по всему датасету ({n} строк), "
                f"затем провели {folds}-fold кросс-валидацию. Что не так?")
        correct = "Кодировка содержит таргет валидационных строк: считать её внутри фолда"
        d = ["Ничего: target encoding безопаснее one-hot", "Нужно было использовать label encoding — он тоже с утечкой",
             "Ошибка только при числе городов больше 100"]
    else:
        stem = (f"StandardScaler обучили (fit) на всём датасете ({n} строк), затем запустили cross_val_score "
                f"с {folds} фолдами. Как сделать корректно?")
        correct = "Обернуть scaler и модель в Pipeline, чтобы fit шёл только на train-фолде"
        d = ["Ничего не менять: масштабирование не использует таргет и не может давать утечку",
             "Масштабировать только валидационные фолды", "Масштабировать после обучения модели"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": d,
        "explanation": "Любое преобразование, обучаемое на данных (отбор признаков, кодирование таргетом, "
                       "оверсэмплинг, масштабирование), должно обучаться только на train-части фолда (Pipeline). "
                       "Для временных рядов — TimeSeriesSplit, для повторяющихся объектов — GroupKFold.",
    }


# --- Статистика: парадокс Симпсона -------------------------------------------------------------------
_SIMPSON = {
    ("A", "A"): "A лучше в каждом сегменте и в целом",
    ("A", "B"): "A лучше в каждом сегменте, но B лучше в целом",
    ("B", "A"): "B лучше в каждом сегменте, но A лучше в целом",
    ("B", "B"): "B лучше в каждом сегменте и в целом",
}


@template(id="data.simpson_paradox", pool="data", topics=["statistics", "ab_testing"], fmt="calc", a=1.3, b=1.5,
          title="Парадокс Симпсона", variants=2000)
def _simpson_paradox(rng: random.Random) -> dict:
    segs = rng.choice([("mobile", "desktop"), ("новые", "старые"), ("Москва", "регионы"), ("iOS", "Android")])
    for _ in range(1000):
        better = rng.choice(["A", "B"])
        worse = "B" if better == "A" else "A"
        r_hi, r_lo = rng.uniform(0.5, 0.8), rng.uniform(0.05, 0.25)
        rates = {better: (r_hi + rng.uniform(0.02, 0.08), r_lo + rng.uniform(0.01, 0.06)), worse: (r_hi, r_lo)}
        if rng.random() < 0.5:  # трафик «лучшего» варианта сосредоточен в слабом сегменте — классический парадокс
            visits = {better: (rng.randint(60, 200), rng.randint(500, 1200)),
                      worse: (rng.randint(500, 1200), rng.randint(60, 200))}
        else:  # похожая структура трафика у обоих вариантов — общий итог совпадает с посегментным
            v1, v2 = rng.randint(200, 900), rng.randint(200, 900)
            visits = {v: (round(v1 * rng.uniform(0.9, 1.1)), round(v2 * rng.uniform(0.9, 1.1))) for v in ("A", "B")}
        conv = {v: tuple(round(rates[v][i] * visits[v][i]) for i in range(2)) for v in ("A", "B")}
        seg_win = []
        for i in range(2):
            ra, rb = conv["A"][i] / visits["A"][i], conv["B"][i] / visits["B"][i]
            seg_win.append("A" if ra > rb else "B" if rb > ra else None)
        ta, tb = sum(conv["A"]) / sum(visits["A"]), sum(conv["B"]) / sum(visits["B"])
        if seg_win[0] is None or seg_win[0] != seg_win[1] or abs(ta - tb) < 0.005:
            continue
        overall = "A" if ta > tb else "B"
        break
    correct = _SIMPSON[(seg_win[0], overall)]
    rows = [f"{segs[i]:<8} | {conv['A'][i]:>4} / {visits['A'][i]:<5}       | {conv['B'][i]:>4} / {visits['B'][i]}"
            for i in range(2)]
    code = "сегмент  | A: покупки / визиты | B: покупки / визиты\n" + "\n".join(rows)
    return {
        "stem": "Результаты A/B-теста конверсии в покупку по двум сегментам трафика. Какой вывод верен?",
        "code": code,
        "code_lang": "text",
        "correct": correct,
        "distractors": [s for s in _SIMPSON.values() if s != correct],
        "explanation": f"В целом: A = {sum(conv['A'])}/{sum(visits['A'])} ≈ {ta:.3f}, B = {sum(conv['B'])}/"
                       f"{sum(visits['B'])} ≈ {tb:.3f}. Если варианты по-разному распределены по сегментам с разной "
                       f"базовой конверсией, общий итог может противоречить посегментному (парадокс Симпсона).",
    }


# --- ML: ROC-AUC вручную -------------------------------------------------------------------------------
@template(id="data.roc_auc", pool="data", topics=["ml"], fmt="calc", a=1.3, b=1.6,
          title="ROC-AUC: смысл и расчёт", variants=2000)
def _roc_auc(rng: random.Random) -> dict:
    for _ in range(1000):
        npos, nneg = rng.choice([(3, 3), (3, 4), (4, 3), (4, 4)])
        labels = [1] * npos + [0] * nneg
        rng.shuffle(labels)
        scores = [round(rng.choice(range(5, 100, 5)) / 100, 2) for _ in labels]
        pos = [s for s, y in zip(scores, labels) if y == 1]
        neg = [s for s, y in zip(scores, labels) if y == 0]
        wins = sum(1.0 if p > q else 0.5 if p == q else 0.0 for p in pos for q in neg)
        auc = wins / (npos * nneg)
        acc = sum((s >= 0.5) == (y == 1) for s, y in zip(scores, labels)) / len(labels)
        strict = sum(p > q for p in pos for q in neg) / (npos * nneg)  # ничьи как 0
        loose = sum(p >= q for p in pos for q in neg) / (npos * nneg)  # ничьи как 1
        if not 0.3 < auc < 0.95 or any(_near_half(v) for v in (auc, acc, 1 - auc, strict, loose)):
            continue
        correct = _f2(auc)
        cands = [_f2(1 - auc), _f2(acc), _f2(strict), _f2(loose), _f2(min(auc + 0.1, 1))]
        if len(set(cands) - {correct}) >= 3:
            break
    code = f"y_true  = {labels}\ny_score = {scores}"
    return {
        "stem": "Чему равен ROC-AUC этих предсказаний? Округлите до сотых.",
        "code": code,
        "code_lang": "python",
        "correct": correct,
        "distractors": cands,
        "explanation": "ROC-AUC — доля пар (положительный, отрицательный), в которых положительный объект получил "
                       f"больший скор (ничья — 0.5): {wins:g} из {npos * nneg}. Порог при этом не нужен.",
    }


# --- A/B-тесты: размер выборки и мощность ------------------------------------------------------------
@template(id="data.ab_sample_size", pool="data", topics=["ab_testing", "statistics"], fmt="calc", a=1.2, b=2.0,
          title="Мощность и размер выборки в A/B-тестах", variants=35)
def _ab_sample_size(rng: random.Random) -> dict:
    kind = rng.choices(["mde", "cuped", "split", "peeking"], weights=[20, 30, 30, 20])[0]
    if kind == "mde":
        k = rng.choice([2, 3, 4, 5])
        n = rng.choice([10_000, 20_000, 50_000])
        stem = (f"Для обнаружения эффекта нужной величины при α = 0.05 и мощности 80% требуется {n:,} пользователей "
                f"в группе. Сколько потребуется, если хотим ловить эффект в {k} {'раза' if k < 5 else 'раз'} меньше?"
                ).replace(",", " ")
        correct = f"{n * k * k:,}".replace(",", " ")
        cands = [f"{x:,}".replace(",", " ") for x in (n * k, n * 2 * k, int(n * math.sqrt(k)), n * k ** 3)]
    elif kind == "cuped":
        n = rng.choice([40_000, 50_000, 80_000, 100_000])
        rho = rng.choice([0.3, 0.5, 0.6, 0.8])
        stem = (f"Без CUPED тесту нужно {n:,} пользователей в группе. Ковариата (метрика до теста) коррелирует с "
                f"целевой метрикой с ρ = {rho}. Сколько пользователей нужно с CUPED при тех же α и мощности?"
                ).replace(",", " ")

        def f(x: float) -> str:
            return f"{round(x):,}".replace(",", " ")

        correct = f(n * (1 - rho ** 2))
        cands = [f(n * (1 - rho)), f(n * rho ** 2), f(n * (1 - rho) ** 2), f(n * math.sqrt(1 - rho ** 2))]
    elif kind == "split":
        big = rng.choice([70, 80, 90, 95])
        small = 100 - big
        ratio = (100 / big + 100 / small) / 4
        stem = (f"Тот же общий трафик делят между контролем и тестом в пропорции {big}/{small} вместо 50/50. Во сколько "
                f"раз вырастет дисперсия оценки разницы средних (дисперсии метрики в группах равны)?")
        correct = _f2(ratio)
        cands = [_f2(50 / small), "1.00", _f2(big / small), _f2(math.sqrt(ratio))]
    else:
        d = rng.choice([7, 10, 14, 20])
        stem = (f"A/B-тест без реального эффекта. Аналитик каждый день в течение {d} дней смотрит p-value и "
                f"останавливает тест при первом p < 0.05. Какой будет реальная доля ложноположительных выводов?")
        correct = f"Больше 5%, но меньше {5 * d}%"
        cands = ["Ровно 5%: α фиксирован заранее", "Меньше 5%: больше проверок — больше уверенности",
                 f"Ровно {5 * d}%: по 5% за каждую проверку"]
    return {
        "stem": stem,
        "correct": correct,
        "distractors": cands,
        "explanation": "Нужный размер выборки ∝ σ²/MDE²: эффект в k раз меньше — выборка в k² раз больше. CUPED "
                       "снижает дисперсию в (1 − ρ²) раз. Дисперсия разницы ∝ 1/n₁ + 1/n₂ — минимальна при 50/50. "
                       "Многократные «подглядывания» раздувают ошибку I рода выше α.",
    }
