"""Самопроверка банка шаблонов: `python -m app.services.bank.selfcheck` из папки backend/.

Проверяет каждый шаблон на 50 зёрнах:
  * генерация без исключений, 4 уникальных варианта, верный индекс в границах;
  * темы шаблона есть в справочнике навыков, пул и формат допустимы, a ∈ [0.5; 2.5], b ∈ [-3; 3];
  * экземпляры с разными зёрнами различаются (уникальных ≥ min(10, variants));
  * для verify=True: выполняет Python-код экземпляра и сравнивает stdout с верным ответом.
Выводит сводку по пулам и распределение сложности относительно порогов грейдов.
"""
import contextlib
import io
import random
import sys
from collections import Counter, defaultdict

from app.dictionaries import GRADES, SKILLS
from app.services.bank import REGISTRY

N_SEEDS = int(sys.argv[1]) if len(sys.argv) > 1 else 50  # `python -m app.services.bank.selfcheck 3000` — расширенная проверка


def _run_python(code: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(code, "<item>", "exec"), {"__name__": "__item__"})  # noqa: S102 — только код из собственного банка
    return buf.getvalue().strip()


def check() -> int:
    errors: list[str] = []
    by_pool: dict[str, list] = defaultdict(list)
    for t in REGISTRY.values():
        by_pool[t.pool].append(t)
        if not (0.5 <= t.a <= 2.5):
            errors.append(f"{t.id}: a={t.a} вне [0.5; 2.5]")
        if not (-3 <= t.b <= 3):
            errors.append(f"{t.id}: b={t.b} вне [-3; 3]")
        for topic in t.topics:
            if topic not in SKILLS:
                errors.append(f"{t.id}: тема {topic} отсутствует в справочнике SKILLS")
        fingerprints = set()
        seeds = list(range(min(N_SEEDS, 50))) + [random.Random(i).randrange(2**31) for i in range(max(0, N_SEEDS - 50))]
        for seed in seeds:
            try:
                inst = t.generate(seed)
            except Exception as e:  # noqa: BLE001
                errors.append(f"{t.id}: seed={seed}: {type(e).__name__}: {e}")
                break
            if len(inst.options) != 4 or len(set(inst.options)) != 4:
                errors.append(f"{t.id}: seed={seed}: варианты не уникальны: {inst.options}")
            if not inst.stem.strip():
                errors.append(f"{t.id}: seed={seed}: пустой текст вопроса")
            fingerprints.add((inst.stem, inst.code, tuple(sorted(inst.options))))
            if t.verify and seed < 50:
                if not inst.code:
                    errors.append(f"{t.id}: verify=True, но нет кода")
                else:
                    try:
                        out = _run_python(inst.code)
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"{t.id}: seed={seed}: код упал: {type(e).__name__}: {e}")
                        continue
                    if out != inst.options[inst.correct_index]:
                        errors.append(f"{t.id}: seed={seed}: stdout={out!r} != верный={inst.options[inst.correct_index]!r}")
        need = min(10, t.variants)
        if len(fingerprints) < need:
            errors.append(f"{t.id}: всего {len(fingerprints)} уникальных экземпляров на {N_SEEDS} зёрнах (нужно ≥ {need})")

    print(f"Шаблонов всего: {len(REGISTRY)}")
    cut = [g["cutoff"] for g in GRADES]
    for pool, items in sorted(by_pool.items()):
        bands = Counter()
        for t in items:
            band = sum(1 for c in cut if t.b >= c)  # 0: ниже стажёра … 4: выше senior
            bands[band] += 1
        fmt = Counter(t.fmt for t in items)
        print(f"  {pool:9s}: {len(items):3d} шаблонов | по полосам сложности {dict(sorted(bands.items()))} | форматы {dict(fmt)}")
    if errors:
        print(f"\nОШИБКИ ({len(errors)}):")
        for e in errors[:200]:
            print("  -", e)
        return 1
    print("\nOK: все шаблоны прошли самопроверку")
    return 0


if __name__ == "__main__":
    sys.exit(check())
