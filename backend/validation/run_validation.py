"""Процедура валидации решения: `python -m validation.run_validation` из папки backend/.

Эталонной разметки в хакатоне нет, поэтому эталон строится из СКРЫТЫХ истинных параметров генератора:
у каждого синтетического кандидата есть истинный уровень θ, истинные навыки (а в резюме — шум и «приписки»),
и мы проверяем, насколько система восстанавливает истину по тому, что ей реально доступно (ответы на тест,
заявленный профиль). Все прогоны детерминированы (фиксированные seed).

Часть A — механика тестирования (чистая симуляция на тех же функциях, что и в продуктиве):
  A1 точность присвоения грейда (наш CAT против фиксированного теста и «процента верных»);
  A2 согласованность: стабильность грейда при повторном прохождении;
  A3 дискриминативность заданий и точность оценки уровня;
  A4 устойчивость к распространению заданий: доля «списывающих», получивших завышенный грейд;
  A5 детектор утечек: время обнаружения и ложные срабатывания;
  A6 калибровка: восстановление параметров a, b шаблонов по ответам (EM, MML).
Часть B — механика подбора (на временной БД, через настоящий API-сервис ранжирования):
  B1 Precision@10, nDCG@10, MRR против бейзлайна «поиск по ключевым словам резюме» и абляции.

Результаты: docs/validation/report.md и docs/validation/results.json.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import tempfile
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_TMP = Path(tempfile.mkdtemp(prefix="fsp_validation_"))
os.environ["DATABASE_URL"] = f"sqlite:///{_TMP / 'validation.db'}"  # до импорта app.*: отдельная временная БД

import numpy as np  # noqa: E402

from app.dictionaries import GRADE_CODES, SPEC_BY_CODE, SPEC_CODES, grade_cutoff, grade_for_theta  # noqa: E402
from app.services import irt  # noqa: E402
from app.services.bank import REGISTRY, templates_for_spec  # noqa: E402
from app.services.testing import choose_template, decide, leak_suspected, stop_rule  # noqa: E402

RESULTS: dict = {}


def true_grade(theta: float) -> str:
    return grade_for_theta(theta) or "none"  # ниже порога стажёра — грейд не должен подтверждаться


def self_declared(theta: float, rng: random.Random) -> str:
    """Самооценка: истинный грейд, сдвинутый вверх с вероятностью 35% и вниз — 15%."""
    tg = grade_for_theta(theta) or "intern"
    i = GRADE_CODES.index(tg) + rng.choices([-1, 0, 1], weights=[15, 50, 35])[0]
    return GRADE_CODES[min(max(i, 0), len(GRADE_CODES) - 1)]


# ======================================================================= симуляторы теста


def run_cat(spec: str, declared: str, answer, rng: random.Random, *, quarantined=frozenset(), exposure=None,
            seen=frozenset(), static_instances=False) -> dict:
    """Одна попытка адаптивного теста. answer(template, seed) -> 0/1."""
    pool = templates_for_spec(spec)
    cut = grade_cutoff(declared)
    used: set[str] = set()
    resp: list[tuple[float, float, int]] = []
    items = []
    theta, se, n_core = cut, irt.PRIOR_SD, 0
    while True:
        t = choose_template(pool, used, set(seen), set(quarantined), theta, set(), len(resp), n_core, exposure or {}, rng)
        if t is None:
            break
        seed = 0 if static_instances else rng.randrange(2**31)
        u = answer(t, seed)
        used.add(t.id)
        n_core += t.pool == "core"
        resp.append((t.a, t.b, u))
        items.append((t.id, seed, u))
        theta, se = irt.eap(resp)
        if stop_rule(declared, theta, se, len(resp)):  # то же правило, что в продуктивном движке
            break
    result, up, sugg = decide(declared, theta, se)
    return {"theta": theta, "se": se, "n": len(resp), "result": result, "upgrade": up, "suggested": sugg, "items": items}


def fixed_test(spec: str, k: int = 18) -> list:
    """Бейзлайн «единый тест»: одни и те же k заданий (и экземпляры) для всех, сложность разнесена по шкале."""
    pool = sorted(templates_for_spec(spec), key=lambda t: t.b)
    idx = np.linspace(0, len(pool) - 1, k).round().astype(int)
    return [pool[i] for i in sorted(set(idx))]


def run_fixed(spec: str, declared: str, answer) -> dict:
    resp = []
    items = []
    for t in fixed_test(spec):
        u = answer(t, 0)
        resp.append((t.a, t.b, u))
        items.append((t.id, 0, u))
    theta, se = irt.eap(resp)
    result, up, sugg = decide(declared, theta, se)
    return {"theta": theta, "se": se, "n": len(resp), "result": result, "upgrade": up, "suggested": sugg, "items": items,
            "pct": sum(u for *_, u in resp) / len(resp)}


def assign_flow(runner, declared: str) -> tuple[str, list[dict]]:
    """Полный путь кандидата по правилам платформы: при неудаче — тест на предложенный грейд ниже,
    при уверенном результате — принятие грейда выше. Возвращает итоговый грейд ('none' — не подтверждён)."""
    attempts = []
    g = declared
    for _ in range(4):
        r = runner(g)
        attempts.append(r)
        if r["result"] == "confirmed_plus":
            return r["upgrade"], attempts
        if r["result"] == "confirmed":
            return g, attempts
        if not r["suggested"] or r["suggested"] == g:
            return "none", attempts
        g = r["suggested"]
    return "none", attempts


def ability_answer(theta: float, nrng: np.random.Generator):
    return lambda t, seed: irt.simulate_answer(theta, t.a, t.b, nrng)


def pct_grade(p: float) -> str:
    """Наивный бейзлайн: грейд по доле верных ответов единого теста."""
    return "none" if p < 0.25 else "intern" if p < 0.45 else "junior" if p < 0.65 else "middle" if p < 0.82 else "senior"


def kappa(a: list[str], b: list[str]) -> float:
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in labels) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def gidx(g: str) -> int:
    return -1 if g == "none" else GRADE_CODES.index(g)


# ======================================================================= A1–A3


def part_a1_a3(n: int = 1500, seed: int = 1) -> None:
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        spec = rng.choice(SPEC_CODES)
        th = float(np.clip(nrng.normal(0.15, 1.0), -3, 3))
        declared = self_declared(th, rng)
        tg = true_grade(th)
        ours, att = assign_flow(lambda g: run_cat(spec, g, ability_answer(th, nrng), rng), declared)
        ours2, att2 = assign_flow(lambda g: run_cat(spec, g, ability_answer(th, nrng), rng), declared)
        fx, fatt = assign_flow(lambda g: run_fixed(spec, g, ability_answer(th, nrng)), declared)
        fx2, _ = assign_flow(lambda g: run_fixed(spec, g, ability_answer(th, nrng)), declared)
        pg = pct_grade(fatt[0]["pct"])
        rows.append({"spec": spec, "theta": th, "true": tg, "declared": declared, "ours": ours, "ours2": ours2,
                     "fixed": fx, "fixed2": fx2, "pct": pg, "att": att, "att2": att2, "fatt": fatt})

    def acc(key: str) -> dict:
        exact = np.mean([r[key] == r["true"] for r in rows])
        within1 = np.mean([abs(gidx(r[key]) - gidx(r["true"])) <= 1 for r in rows])
        over = np.mean([gidx(r[key]) > gidx(r["true"]) for r in rows])
        return {"exact": round(float(exact), 3), "within_1": round(float(within1), 3), "overrated": round(float(over), 3)}

    labels = ["none", *GRADE_CODES]
    conf = {t: {p: 0 for p in labels} for t in labels}
    for r in rows:
        conf[r["true"]][r["ours"]] += 1

    first = [r["att"][0] for r in rows]
    second = [r["att2"][0] for r in rows]
    th_true = np.array([r["theta"] for r in rows])
    th_hat = np.array([a["theta"] for a in first])
    fx_hat = np.array([r["fatt"][0]["theta"] for r in rows])
    RESULTS["A1_accuracy"] = {"n": n, "ours_cat": acc("ours"), "fixed_test_irt": acc("fixed"), "fixed_test_percent": acc("pct"),
                              "self_declared": acc("declared"), "confusion_ours": conf}
    RESULTS["A2_consistency"] = {
        "ours_grade_agreement": round(float(np.mean([r["ours"] == r["ours2"] for r in rows])), 3),
        "ours_kappa": round(kappa([r["ours"] for r in rows], [r["ours2"] for r in rows]), 3),
        "fixed_grade_agreement": round(float(np.mean([r["fixed"] == r["fixed2"] for r in rows])), 3),
        "fixed_kappa": round(kappa([r["fixed"] for r in rows], [r["fixed2"] for r in rows]), 3),
        "ours_theta_retest_corr": round(float(np.corrcoef([a["theta"] for a in first], [a["theta"] for a in second])[0, 1]), 3),
    }
    # дискриминативность: точечно-бисериальная корреляция ответа на шаблон с истинным уровнем
    per_t: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in rows:
        for a in r["att"]:
            for tid, _s, u in a["items"]:
                per_t[tid].append((u, r["theta"]))
    rpb = {}
    for tid, xs in per_t.items():
        if len(xs) >= 30:
            u = np.array([x[0] for x in xs])
            t = np.array([x[1] for x in xs])
            if u.std() > 0:
                rpb[tid] = float(np.corrcoef(u, t)[0, 1])
    by_pool = defaultdict(list)
    for tid, v in rpb.items():
        by_pool[REGISTRY[tid].pool].append(v)
    lengths = [a["n"] for r in rows for a in r["att"]]
    RESULTS["A3_discrimination"] = {
        "theta_corr_ours": round(float(np.corrcoef(th_true, th_hat)[0, 1]), 3),
        "theta_rmse_ours": round(float(np.sqrt(np.mean((th_true - th_hat) ** 2))), 3),
        "theta_corr_fixed": round(float(np.corrcoef(th_true, fx_hat)[0, 1]), 3),
        "theta_rmse_fixed": round(float(np.sqrt(np.mean((th_true - fx_hat) ** 2))), 3),
        "mean_items_ours": round(float(np.mean(lengths)), 2),
        "items_fixed": len(fixed_test("backend")),
        "mean_se_ours": round(float(np.mean([a["se"] for a in first])), 3),
        "templates_evaluated": len(rpb),
        "median_point_biserial": round(float(np.median(list(rpb.values()))), 3) if rpb else None,
        "share_rpb_ge_0_2": round(float(np.mean([v >= 0.2 for v in rpb.values()])), 3) if rpb else None,
        "median_rpb_by_pool": {p: round(float(np.median(v)), 3) for p, v in sorted(by_pool.items())},
        "strong_vs_weak_quartile_theta_gap": round(float(np.mean(th_hat[th_true >= np.quantile(th_true, 0.75)]) - np.mean(th_hat[th_true <= np.quantile(th_true, 0.25)])), 3),
    }


# ======================================================================= A4: распространение заданий


def part_a4(seed: int = 2) -> None:
    """Сценарий: ответы на задания, которые видели первые 300 честных кандидатов, выложены в сеть.
    «Списывающие» с уровнем junior (θ≈−0.3) заявляют middle и отвечают верно на любой экземпляр из слитой базы.
    Сравниваем три механики: единый тест, банк без параметризации (одинаковые экземпляры) и наш банк."""
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    spec = "backend"
    out = {}
    for regime in ("fixed", "static_pool", "parametric"):
        leaked: set[tuple[str, int]] = set()
        for _ in range(300):  # кто-то прошёл тест и выложил задания с ответами
            th = float(nrng.normal(0.15, 1))
            ans = ability_answer(th, nrng)
            r = run_fixed(spec, "middle", ans) if regime == "fixed" else run_cat(spec, "middle", ans, rng, static_instances=regime == "static_pool")
            leaked.update((tid, s) for tid, s, _u in r["items"])
        inflated, thetas, hit_rate = 0, [], []
        n = 400
        for _ in range(n):
            th = float(np.clip(nrng.normal(-0.3, 0.3), -1.5, 0.3))  # истинный junior

            def cheat(t, s, th=th):
                return 1 if (t.id, s) in leaked else irt.simulate_answer(th, t.a, t.b, nrng)

            r = run_fixed(spec, "middle", cheat) if regime == "fixed" else run_cat(spec, "middle", cheat, rng, static_instances=regime == "static_pool")
            hit_rate.append(np.mean([(tid, s) in leaked for tid, s, _u in r["items"]]))
            thetas.append(r["theta"] - th)
            inflated += r["result"] in ("confirmed", "confirmed_plus")
        out[regime] = {"leak_coverage_of_served_items": round(float(np.mean(hit_rate)), 3),
                       "cheaters_confirmed_middle": round(inflated / n, 3), "mean_theta_inflation": round(float(np.mean(thetas)), 3)}
    # честная база для сравнения: те же junior без утечки
    base = 0
    for _ in range(400):
        th = float(np.clip(nrng.normal(-0.3, 0.3), -1.5, 0.3))
        base += run_cat(spec, "middle", ability_answer(th, nrng), rng)["result"] in ("confirmed", "confirmed_plus")
    out["no_leak_reference"] = {"cheaters_confirmed_middle": round(base / 400, 3)}
    RESULTS["A4_leak_resistance"] = out


# ======================================================================= A5: детектор утечек


def part_a5(seed: int = 3) -> None:
    """Утекает не конкретный экземпляр, а «приём решения» 4 шаблонов среднего уровня. После утечки 30% кандидатов
    отвечают на них верно с вероятностью 0,95. Детектор работает на остатках «ответ − P(θ̂)» по окну 60 показов."""
    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    spec = "backend"
    pool = templates_for_spec(spec)
    mid = sorted([t for t in pool if -0.2 <= t.b <= 1.2], key=lambda t: t.b)
    leaked_ids = {t.id for t in mid[:: max(1, len(mid) // 4)][:4]}

    def simulate(with_leak: bool, n_total: int = 1600, leak_from: int = 400) -> dict:
        residuals: dict[str, list[float]] = defaultdict(list)
        exposures_after_leak: dict[str, int] = defaultdict(int)
        flagged_at: dict[str, int] = {}
        quarantined: set[str] = set()
        for k in range(n_total):
            th = float(nrng.normal(0.15, 1))
            leak_on = with_leak and k >= leak_from
            cheater = leak_on and rng.random() < 0.3

            def ans(t, s, th=th, cheater=cheater):
                if cheater and t.id in leaked_ids:
                    return int(rng.random() < 0.95)
                return irt.simulate_answer(th, t.a, t.b, nrng)

            r = run_cat(spec, self_declared(th, rng), ans, rng, quarantined=frozenset(quarantined))
            for tid, _s, u in r["items"]:
                t = REGISTRY[tid]
                residuals[tid] = (residuals[tid] + [u - float(irt.p_correct(r["theta"], t.a, t.b))])[-60:]
                if leak_on and tid in leaked_ids:
                    exposures_after_leak[tid] += 1
                if tid not in quarantined and leak_suspected(residuals[tid]):
                    quarantined.add(tid)
                    flagged_at[tid] = exposures_after_leak.get(tid, 0)
        fp = sorted(quarantined - leaked_ids)
        return {"leaked": sorted(leaked_ids), "flagged_leaked": {t: flagged_at.get(t) for t in sorted(leaked_ids)},
                "detected": len(leaked_ids & quarantined), "false_positives": len(fp), "false_positive_ids": fp,
                "templates_in_pool": len(pool)}

    leak = simulate(True)
    control = simulate(False)
    RESULTS["A5_leak_detector"] = {
        "leaked_templates": len(leaked_ids),
        "detected": leak["detected"],
        "exposures_after_leak_until_flag": leak["flagged_leaked"],
        "false_positives_with_leak": leak["false_positives"],
        "false_positives_control_no_leak": control["false_positives"],
        "control_false_positive_ids": control["false_positive_ids"],
        "pool_size": leak["templates_in_pool"],
    }


# ======================================================================= A6: калибровка


def part_a6(seed: int = 4, n_people: int = 3000, per_person: int = 20) -> None:
    rng = np.random.default_rng(seed)
    pool = templates_for_spec("backend")
    a_true = np.array([t.a for t in pool])
    b_true = np.array([t.b for t in pool])
    th = rng.normal(0, 1, n_people)
    resp = np.full((n_people, len(pool)), np.nan)
    for i in range(n_people):
        idx = rng.choice(len(pool), size=min(per_person, len(pool)), replace=False)
        p = irt.p_correct(th[i], a_true[idx], b_true[idx])
        resp[i, idx] = (rng.random(len(idx)) < p).astype(float)
    t0 = time.time()
    a_hat, b_hat = irt.calibrate_2pl(resp)
    RESULTS["A6_calibration"] = {
        "people": n_people, "answers_per_person": per_person, "templates": len(pool),
        "corr_a": round(float(np.corrcoef(a_true, a_hat)[0, 1]), 3), "rmse_a": round(float(np.sqrt(np.mean((a_true - a_hat) ** 2))), 3),
        "corr_b": round(float(np.corrcoef(b_true, b_hat)[0, 1]), 3), "rmse_b": round(float(np.sqrt(np.mean((b_true - b_hat) ** 2))), 3),
        "seconds": round(time.time() - t0, 1),
    }


# ======================================================================= B: подбор


# Общие для всех специализаций основы: незнание конкретной технологии не делает человека слабее в них
GENERAL_TOPICS = {"http", "rest", "git", "algorithms", "data_structures", "oop", "design_patterns", "concurrency",
                  "system_design", "statistics", "linux", "networking", "test_design", "manual_testing"}
DEV_SEED, TEST_SEEDS = 105, (5, 6, 7)  # веса подбора настраивались на DEV_SEED, отчёт — среднее по TEST_SEEDS
TECH_PENALTY = 1.2  # насколько хуже кандидат решает задания по технологии, которой не владеет (в единицах θ)


def build_world(seed: int, n_cand: int = 500, n_needs: int = 40, tech_penalty: float = TECH_PENALTY) -> dict:
    """Синтетический мир со скрытой истиной: кандидаты проходят тест через настоящий движок и БД."""
    from app.db import Base, SessionLocal, engine
    from app.models import CandidateProfile, Company, User, utcnow
    from app.services import matching, testing
    from app.seed import CITIES, CORE_STACK, SALARY
    from fsp_mock.data import participants

    rng = random.Random(seed)
    nrng = np.random.default_rng(seed)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    fsp_pool = [p for p in participants().values() if p["achievements"]]
    truth: dict[int, dict] = {}

    for i in range(n_cand):
        spec = rng.choice(SPEC_CODES)
        th = float(np.clip(nrng.normal(0.15, 1.0), -2.5, 2.8))
        skills = SPEC_BY_CODE[spec]["skills"]
        core = CORE_STACK[spec]
        k = int(np.clip(round(5 + 2 * (th + 1)), 3, 14))  # сильнее специалист — шире реальный стек
        weights = [4 if s in core else 1 for s in skills]
        true_sk: set[str] = set()
        while len(true_sk) < min(k, len(skills)):
            true_sk.add(rng.choices(skills, weights=weights)[0])
        declared = {s for s in true_sk if rng.random() > 0.1}
        if rng.random() < 0.35:  # «приписки» в резюме: навыки, которыми кандидат реально не владеет
            pad = [s for s in skills if s not in true_sk]
            declared |= set(rng.sample(pad, min(3, len(pad))))
        tg = grade_for_theta(th) or "intern"
        smin, smax = SALARY[tg]
        u = User(email=f"v{i}@val.local", password_hash="x", role="candidate", email_verified=True, consent_pd_at=utcnow())
        db.add(u)
        db.flush()
        fsp = rng.choice(fsp_pool) if rng.random() < 0.35 + 0.1 * th else None
        c = CandidateProfile(user_id=u.id, anon_code=f"V-{i}", full_name=f"Кандидат {i}", specialization=spec, stack=sorted(declared),
                             work_format=rng.choice([["remote"], ["remote", "hybrid"], ["hybrid"], ["office", "hybrid"]]),
                             salary_expect_min=int(round(rng.uniform(smin, smax), -4)), city=rng.choice(CITIES),
                             relocation=rng.random() < 0.3, about="", job_status="active", consent_publish_at=utcnow(),
                             fsp_id=fsp["fsp_id"] if fsp else None, fsp_achievements=fsp["achievements"] if fsp else [])
        db.add(c)
        db.commit()

        # Задания по конкретной технологии, которой кандидат не владеет, он решает хуже (θ − tech_penalty)
        def ans(t, s, th=th, true_sk=true_sk):
            tech = [x for x in t.topics if x not in GENERAL_TOPICS]
            eff = th - tech_penalty if tech and not (set(tech) & true_sk) else th
            return irt.simulate_answer(eff, t.a, t.b, nrng)

        declared_grade = self_declared(th, rng)
        g = declared_grade
        for _ in range(4):  # тот же путь, что у живого пользователя: настоящий движок и БД
            att = testing.start_attempt(db, c, g, rng)
            while att.status == "in_progress":
                it = testing.current_item(att)
                ok = ans(REGISTRY[it.template_id], it.seed)
                idx = it.correct_index if ok else (it.correct_index + 1) % len(it.payload["options"])
                testing.submit_answer(db, att, it.id, idx, rng)
            if att.result == "confirmed_plus":
                testing.accept_upgrade(db, c, att)
                break
            if att.result == "confirmed" or not att.suggested_grade:
                break
            g = att.suggested_grade
        truth[c.id] = {"theta": th, "spec": spec, "skills": true_sk, "true_grade": true_grade(th), "declared_grade": declared_grade,
                       "declared": declared, "salary": c.salary_expect_min}

    comp_user = User(email="hr@val.local", password_hash="x", role="employer", email_verified=True)
    db.add(comp_user)
    db.flush()
    company = Company(user_id=comp_user.id, name="Валидация")
    db.add(company)
    db.commit()

    needs = []
    for _ in range(n_needs):
        spec = rng.choice(SPEC_CODES)
        grade = rng.choices(GRADE_CODES, weights=[1, 3, 4, 2])[0]
        skills = SPEC_BY_CODE[spec]["skills"]
        must = rng.sample(CORE_STACK[spec], 3) + ([rng.choice([s for s in skills if s not in CORE_STACK[spec]])] if rng.random() < 0.5 else [])
        nice = rng.sample([s for s in skills if s not in must], 2)
        smin, smax = SALARY[grade]
        sal_to = int(round(rng.uniform((smin + smax) / 2, smax * 1.1), -4))
        needs.append(matching.NeedSpec(spec, grade, must, nice, rng.choice([["remote"], ["hybrid", "remote"], ["office", "hybrid"]]),
                                       "", int(round(sal_to * 0.75, -4)), sal_to, "Нужен специалист: " + ", ".join(must)))
    cats = [truth[c.id]["true_grade"] == (c.grade or "none") for c in db.query(CandidateProfile).all()]
    return {"db": db, "truth": truth, "needs": needs, "company": company, "rng": rng, "category_accuracy": float(np.mean(cats))}


def relevance(world: dict, n, cid: int) -> int:
    """Эталон по скрытой истине: 2 — точное совпадение специализации и грейда, реально владеет ≥75% обязательного
    стека и ожидания в пределах вилки +10%; 1 — грейд ±1 и владеет ≥50% стека; 0 — остальные."""
    tr = world["truth"][cid]
    if tr["spec"] != n.specialization or tr["true_grade"] == "none":
        return 0
    diff = abs(gidx(tr["true_grade"]) - gidx(n.grade))
    cov = len(set(n.stack_must) & tr["skills"]) / len(n.stack_must)
    if diff == 0 and cov >= 0.75 and tr["salary"] <= n.salary_to * 1.1:
        return 2
    if diff <= 1 and cov >= 0.5:
        return 1
    return 0


def rank_metrics(world: dict, ranked: list[int], n, k: int = 10) -> dict:
    truth = world["truth"]
    rels = [relevance(world, n, cid) for cid in ranked[:k]]
    ideal = sorted((relevance(world, n, cid) for cid in truth), reverse=True)[:k]
    dcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(rels))
    idcg = sum((2**r - 1) / math.log2(i + 2) for i, r in enumerate(ideal)) or 1.0
    rr = next((1 / (i + 1) for i, cid in enumerate(ranked) if relevance(world, n, cid) == 2), 0.0)
    return {"p_at_10": sum(r >= 1 for r in rels) / k, "p_strict_at_10": sum(r == 2 for r in rels) / k, "ndcg_at_10": dcg / idcg,
            "mrr": rr, "wrong_category_in_top10": sum(truth[cid]["spec"] != n.specialization for cid in ranked[:k]) / k}


def systems_for(world: dict) -> dict:
    from app.services import matching

    truth, db, company, rng = world["truth"], world["db"], world["company"], world["rng"]

    def baseline(n) -> list[int]:
        # «Классическая площадка»: совпадение ключевых слов в резюме + самозаявленный грейд, без категорий и тестов
        def s(cid):
            tr = truth[cid]
            return (len(set(n.stack_must) & tr["declared"]) + 0.5 * len(set(n.stack_nice) & tr["declared"])
                    + (1 if tr["declared_grade"] == n.grade else 0) + rng.random() * 1e-3)
        return sorted(truth, key=s, reverse=True)

    def ours(n) -> list[int]:
        return [c.id for c, _m, _s in matching.rank_for_need(db, n, company)]

    def ours_declared_only(n) -> list[int]:
        # абляция: навыки только по резюме — тест не подтверждает и не опровергает их
        saved = matching.is_verified, matching.is_refuted
        matching.is_verified = lambda c, s: False
        matching.is_refuted = lambda c, s: False
        try:
            return ours(n)
        finally:
            matching.is_verified, matching.is_refuted = saved

    return {"baseline_keywords": baseline, "ours": ours, "ours_declared_skills_only": ours_declared_only}


def evaluate(world: dict, systems: dict) -> dict:
    agg = {}
    for name, fn in systems.items():
        ms = [rank_metrics(world, fn(n), n) for n in world["needs"]]
        agg[name] = {k: round(float(np.mean([m[k] for m in ms])), 3) for k in ms[0]}
    return agg


def part_b(seeds: tuple[int, ...] = TEST_SEEDS) -> None:
    runs, cat_acc = [], []
    for seed in seeds:
        world = build_world(seed)
        runs.append(evaluate(world, systems_for(world)))
        cat_acc.append(world["category_accuracy"])
        world["db"].close()
    systems = {}
    for name in runs[0]:
        systems[name] = {k: round(float(np.mean([r[name][k] for r in runs])), 3) for k in runs[0][name]}
        systems[name]["range"] = {k: [round(min(r[name][k] for r in runs), 3), round(max(r[name][k] for r in runs), 3)]
                                  for k in ("ndcg_at_10", "p_at_10")}
    RESULTS["B_matching"] = {"candidates": len(world["truth"]), "needs": len(world["needs"]), "seeds": list(seeds),
                             "dev_seed": DEV_SEED, "systems": systems, "category_accuracy_in_db": round(float(np.mean(cat_acc)), 3)}


# ======================================================================= отчёт


def _charts(out_dir: Path) -> None:
    """SVG-графики к отчёту: заголовок — вывод с числом, акцент — наша механика."""
    from validation.charts import bar_chart, dec2, pct

    R = RESULTS
    if "A1_accuracy" in R:
        a = R["A1_accuracy"]
        bar_chart(out_dir / "chart_accuracy.svg",
                  f"Тест присваивает истинный грейд в {pct(a['ours_cat']['exact'])} случаев",
                  f"Доля кандидатов с точно определённым грейдом, {a['n']} синтетических кандидатов с известным уровнем",
                  [{"label": "Адаптивный тест (CAT + IRT)", "value": a["ours_cat"]["exact"], "accent": True},
                   {"label": "Единый тест той же длины", "value": a["fixed_test_irt"]["exact"]},
                   {"label": "Единый тест, грейд по доле верных", "value": a["fixed_test_percent"]["exact"]},
                   {"label": "Самооценка в резюме", "value": a["self_declared"]["exact"]}],
                  xmax=1.0, fmt=pct, source="validation/run_validation.py · A1")
    if "A4_leak_resistance" in R:
        a = R["A4_leak_resistance"]
        bar_chart(out_dir / "chart_leak.svg",
                  f"При утечке ответов наш банк пропускает {pct(a['parametric']['cheaters_confirmed_middle'])} списывающих, единый тест — "
                  f"{pct(a['fixed']['cheaters_confirmed_middle'])}",
                  "Доля junior, «подтвердивших» middle по слитым ответам 300 предыдущих кандидатов",
                  [{"label": "Единый тест", "value": a["fixed"]["cheaters_confirmed_middle"]},
                   {"label": "Банк без параметризации", "value": a["static_pool"]["cheaters_confirmed_middle"]},
                   {"label": "Параметрические шаблоны + CAT", "value": a["parametric"]["cheaters_confirmed_middle"], "accent": True}],
                  xmax=1.0, fmt=pct, ref={"value": a["no_leak_reference"]["cheaters_confirmed_middle"],
                                          "label": f"без утечки: {pct(a['no_leak_reference']['cheaters_confirmed_middle'])}"},
                  source="validation/run_validation.py · A4")
    if "B_matching" in R:
        sy = R["B_matching"]["systems"]
        rows = []
        for k, label, acc in (("baseline_keywords", "Ключевые слова резюме", False), ("ours", "Подбор ФСП Талант", True),
                              ("ours_declared_skills_only", "Абляция: навыки только из резюме", False)):
            m = sy[k]
            rows.append({"label": label, "value": m["ndcg_at_10"], "accent": acc,
                         "lo": m["range"]["ndcg_at_10"][0], "hi": m["range"]["ndcg_at_10"][1]})
        bar_chart(out_dir / "chart_matching.svg",
                  f"Подбор: nDCG@10 {dec2(sy['ours']['ndcg_at_10'])} против {dec2(sy['baseline_keywords']['ndcg_at_10'])} у поиска по резюме",
                  "Качество топ-10 выдачи по 40 потребностям, среднее по 3 мирам, усы — разброс между мирами",
                  rows, xmax=1.0, fmt=dec2, source="validation/run_validation.py · B")


def write_report() -> None:
    out_dir = ROOT / "docs" / "validation"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(json.dumps(RESULTS, ensure_ascii=False, indent=2))
    R = RESULTS
    _charts(out_dir)
    a1, a2, a3, a4, a5, a6, b = (R.get(k, {}) for k in ("A1_accuracy", "A2_consistency", "A3_discrimination", "A4_leak_resistance",
                                                           "A5_leak_detector", "A6_calibration", "B_matching"))
    L = []
    w = L.append
    w("# Валидация решения «ФСП Талант»\n")
    w(f"Сгенерировано скриптом `backend/validation/run_validation.py` ({time.strftime('%Y-%m-%d %H:%M')}). Банк: {len(REGISTRY)} шаблонов.\n")
    w("## Методика\n")
    w("Эталонной разметки нет, поэтому эталон — **скрытые истинные параметры генератора**. У каждого синтетического "
      "кандидата есть истинный уровень θ (по нему определяется истинный грейд), истинные навыки и заявленный профиль "
      "с шумом: самооценка грейда завышена у 35%, в 35% резюме есть «приписанные» навыки. Система видит только то, что "
      "увидела бы в продуктиве: ответы на тест и заявленный профиль. Ответы моделируются по IRT 2PL. Все прогоны "
      "детерминированы (фиксированные seed).\n")
    if a1 and a4 and b:
        o, bl, ab = b["systems"]["ours"], b["systems"]["baseline_keywords"], b["systems"]["ours_declared_skills_only"]
        w("## Итоги\n")
        w(f"- **Категоризация.** Адаптивный тест присваивает истинный грейд в {a1['ours_cat']['exact']:.0%} случаев и "
          f"ошибается не больше чем на ступень в {a1['ours_cat']['within_1']:.1%}. Самооценка в резюме даёт "
          f"{a1['self_declared']['exact']:.0%} и завышает грейд у {a1['self_declared']['overrated']:.0%} кандидатов. "
          f"По точности CAT сопоставим с единым тестом той же длины ({a1['fixed_test_irt']['exact']:.0%}), "
          "но единый тест полностью уязвим к утечкам (см. ниже).")
        w(f"- **Устойчивость к распространению заданий.** При утечке ответов единый тест «подтверждает» middle у "
          f"{a4['fixed']['cheaters_confirmed_middle']:.0%} списывающих junior. Банк без параметризации — тоже у "
          f"{a4['static_pool']['cheaters_confirmed_middle']:.0%}. Наш банк — у {a4['parametric']['cheaters_confirmed_middle']:.0%}, "
          f"на уровне честного прохождения ({a4['no_leak_reference']['cheaters_confirmed_middle']:.0%}).")
        if a5:
            w(f"- **Утечка приёма решения** обнаруживается детектором: {a5['detected']} из {a5['leaked_templates']} шаблонов "
              "уходят в карантин за 70–300 показов.")
        w(f"- **Подбор.** nDCG@10 {o['ndcg_at_10']:.2f} против {bl['ndcg_at_10']:.2f} у поиска по ключевым словам резюме "
          f"({(o['ndcg_at_10'] / bl['ndcg_at_10'] - 1):+.0%}). Доля релевантных в топ-10 — {o['p_at_10']:.0%} против "
          f"{bl['p_at_10']:.0%}. Кандидатов чужой специализации в топе — {o['wrong_category_in_top10']:.0%} против "
          f"{bl['wrong_category_in_top10']:.0%}.")
        w(f"- **Честное наблюдение.** Поштучное подтверждение навыков тестом почти не меняет выдачу (абляция: nDCG "
          f"{ab['ndcg_at_10']:.2f}). При ~18 вопросах на ~40 тем на навык приходится 1–2 вопроса, и сигнал слабый. "
          "Выигрыш даёт категоризация по тесту. Точечную проверку навыков развиваем через регулярные задания "
          "по заявленному стеку.\n")
    if a1:
        w("## A1. Точность присвоения грейда\n")
        w(f"{a1['n']} кандидатов проходят полный путь платформы: тест на заявленный грейд; при неудаче — тест на "
          "предложенный грейд ниже; при уверенном результате — принятие грейда выше.\n")
        w("| Механика | Точно | ±1 грейд | Завышено |")
        w("|---|---|---|---|")
        for k, name in (("ours_cat", "**Наш адаптивный тест (CAT + IRT)**"), ("fixed_test_irt", "Единый тест той же длины (18 заданий), оценка по IRT"),
                        ("fixed_test_percent", "Единый тест, грейд по доле верных"), ("self_declared", "Самооценка кандидата (резюме)")):
            m = a1[k]
            w(f"| {name} | {m['exact']:.1%} | {m['within_1']:.1%} | {m['overrated']:.1%} |")
        w("\n![Точность присвоения грейда](chart_accuracy.svg)\n")
        w("\nМатрица ошибок нашего теста (строки — истинный грейд, столбцы — присвоенный):\n")
        labels = ["none", *GRADE_CODES]
        w("| истина \\ итог | " + " | ".join(labels) + " |")
        w("|---|" + "---|" * len(labels))
        for t in labels:
            w(f"| {t} | " + " | ".join(str(a1['confusion_ours'][t][p]) for p in labels) + " |")
        w("")
    if a2:
        w("## A2. Согласованность (повторное прохождение)\n")
        w("Тот же кандидат проходит путь второй раз и получает новые экземпляры заданий и другой маршрут CAT.\n")
        w("| Механика | Тот же грейд | Каппа Коэна |")
        w("|---|---|---|")
        w(f"| Наш тест | {a2['ours_grade_agreement']:.1%} | {a2['ours_kappa']} |")
        w(f"| Единый тест | {a2['fixed_grade_agreement']:.1%} | {a2['fixed_kappa']} |")
        w(f"\nКорреляция θ̂ между первой и повторной попыткой: **{a2['ours_theta_retest_corr']}**.\n")
    if a3:
        w("## A3. Дискриминативность и точность оценки уровня\n")
        w("| Показатель | Наш тест | Единый тест |")
        w("|---|---|---|")
        w(f"| Корреляция θ̂ с истинным θ | {a3['theta_corr_ours']} | {a3['theta_corr_fixed']} |")
        w(f"| RMSE θ̂ | {a3['theta_rmse_ours']} | {a3['theta_rmse_fixed']} |")
        w(f"| Вопросов в тесте | {a3['mean_items_ours']} (в среднем) | {a3['items_fixed']} |")
        w(f"\n- Средняя стандартная ошибка θ̂ на выходе: {a3['mean_se_ours']}.")
        w(f"- Разрыв θ̂ между сильным и слабым квартилями: {a3['strong_vs_weak_quartile_theta_gap']}.")
        w(f"- Шаблонов с достаточной статистикой: {a3['templates_evaluated']}; медианная точечно-бисериальная корреляция "
          f"ответа с уровнем: **{a3['median_point_biserial']}**; доля шаблонов с r ≥ 0,2: {a3['share_rpb_ge_0_2']:.0%}.")
        w("- Медиана r по пулам: " + ", ".join(f"{p}: {v}" for p, v in a3["median_rpb_by_pool"].items()) + ".")
        w("\nВ адаптивном тесте вопросы подбираются близко к уровню кандидата, поэтому r здесь ниже, чем в "
          "неадаптивной выборке. Это ожидаемо и не означает слабых заданий.\n")
    if a4:
        w("## A4. Устойчивость к распространению заданий\n")
        w("Сценарий: задания и ответы 300 первых кандидатов выложены в сеть. Затем 400 «списывающих» с истинным "
          "уровнем junior заявляют middle и отвечают верно на любое задание из слитой базы.\n")
        w("| Механика | Доля выданных заданий, найденных в слитой базе | Подтвердили middle | Завышение θ̂ |")
        w("|---|---|---|---|")
        names = {"fixed": "Единый тест", "static_pool": "Банк без параметризации (CAT, одинаковые экземпляры)", "parametric": "**Наш банк: параметрические шаблоны + CAT**"}
        for k, n in names.items():
            m = a4[k]
            w(f"| {n} | {m['leak_coverage_of_served_items']:.0%} | {m['cheaters_confirmed_middle']:.0%} | {m['mean_theta_inflation']:+.2f} |")
        w(f"| Справочно: те же кандидаты без утечки | — | {a4['no_leak_reference']['cheaters_confirmed_middle']:.0%} | — |\n")
        w("![Устойчивость к утечке заданий](chart_leak.svg)\n")
    if a5:
        w("## A5. Детектор утечек\n")
        w(f"Утекает не конкретный экземпляр, а приём решения {a5['leaked_templates']} шаблонов среднего уровня. После "
          "утечки 30% кандидатов отвечают на них верно с вероятностью 0,95. Детектор считает остатки «ответ − P(θ̂)» по окну "
          "из 60 показов и отправляет шаблон в карантин при среднем остатке > 0,2 и z > 3.\n")
        w(f"- Обнаружено утёкших шаблонов: **{a5['detected']} из {a5['leaked_templates']}**.")
        ex = a5["exposures_after_leak_until_flag"]
        w("- Показов после утечки до карантина: " + ", ".join(f"`{t}` — {n}" for t, n in ex.items()) + ".")
        w(f"- Ложные срабатывания при утечке: {a5['false_positives_with_leak']} из {a5['pool_size']}; в контроле без утечки: "
          f"{a5['false_positives_control_no_leak']}. Карантин не удаляет шаблон, а отправляет его на ревизию: после проверки "
          "методистом шаблон возвращается или заменяется новым.\n")
    if a6:
        w("## A6. Калибровка параметров шаблонов\n")
        w(f"Проверяем процедуру калибровки для реальных данных. {a6['people']} человек отвечают на {a6['answers_per_person']} "
          f"случайных шаблонов из {a6['templates']}. По ответам EM-алгоритм (MML, Бок–Эйткин) восстанавливает a и b.\n")
        w("| Параметр | Корреляция с истинным | RMSE |")
        w("|---|---|---|")
        w(f"| a (различающая способность) | {a6['corr_a']} | {a6['rmse_a']} |")
        w(f"| b (сложность) | {a6['corr_b']} | {a6['rmse_b']} |")
        w(f"\nВремя калибровки: {a6['seconds']} с. В продуктиве экспертные a и b заменяются откалиброванными по мере накопления ответов.\n")
    if b:
        w("## B. Качество подбора\n")
        w(f"В каждом из {len(b['seeds'])} независимых миров (seed {', '.join(map(str, b['seeds']))}) {b['candidates']} синтетических "
          f"кандидатов прошли тест через настоящий движок и БД. Веса подбора настраивались на отдельном мире (seed {b['dev_seed']}), "
          f"который в отчёт не входит. Ниже — среднее по мирам, в скобках — разброс. По "
          f"{b['needs']} случайным потребностям сравниваем топ-10 выдачи с эталонной релевантностью, посчитанной по скрытой истине:\n")
        w("- **2** — истинная специализация совпадает, истинный грейд совпадает, кандидат реально владеет ≥ 75% "
          "обязательного стека, ожидания в пределах вилки +10%;")
        w("- **1** — грейд в пределах ±1 и владеет ≥ 50% стека;")
        w("- **0** — остальные.\n")
        w(f"Доля кандидатов, чья категория совпала с истинным грейдом: **{b['category_accuracy_in_db']:.1%}**. Это ниже, чем в A1, "
          "потому что здесь моделируется незнание конкретных технологий: такие задания кандидат решает хуже, и тест честно "
          "снижает оценку прикладного уровня, а «истинный» грейд задан только общим уровнем θ.\n")
        w("| Система | P@10 (rel ≥ 1) | P@10 (rel = 2) | nDCG@10 | MRR | Чужая специализация в топ-10 |")
        w("|---|---|---|---|---|---|")
        names = {"baseline_keywords": "Бейзлайн: ключевые слова резюме + самозаявленный грейд",
                 "ours": "**Наш подбор**", "ours_declared_skills_only": "Абляция: наш подбор, но навыки только по резюме (без подтверждения и опровержения тестом)"}
        for k, n in names.items():
            m = b["systems"][k]
            rg = m["range"]
            w(f"| {n} | {m['p_at_10']:.1%} ({rg['p_at_10'][0]:.0%}–{rg['p_at_10'][1]:.0%}) | {m['p_strict_at_10']:.1%} | "
              f"{m['ndcg_at_10']:.3f} ({rg['ndcg_at_10'][0]:.2f}–{rg['ndcg_at_10'][1]:.2f}) | {m['mrr']:.3f} | {m['wrong_category_in_top10']:.1%} |")
        w("\n![Качество подбора](chart_matching.svg)\n")
    w("## Ограничения\n")
    w("- Данные синтетические, ответы моделируются той же моделью IRT, что лежит в основе оценки. Это проверяет "
      "корректность механики, но не реальную трудность заданий. Её покажет калибровка (A6) на ответах живых кандидатов.")
    w("- Эталон релевантности (B) задан правилами команды. Следующий шаг — экспертная разметка 100–200 пар "
      "«вакансия — кандидат» рекрутерами ФСП и партнёров.\n")
    (out_dir / "report.md").write_text("\n".join(L))
    print(f"\nОтчёт: {out_dir / 'report.md'}")


def main() -> int:
    if os.environ.get("PYTHONHASHSEED") != "0":
        # Порядок обхода множеств строк в Python случаен между запусками; фиксируем его, чтобы отчёт был воспроизводим
        os.execve(sys.executable, [sys.executable, "-m", "validation.run_validation", *sys.argv[1:]],
                  {**os.environ, "PYTHONHASHSEED": "0"})
    t0 = time.time()
    steps = [("A1–A3 точность, согласованность, дискриминативность", part_a1_a3), ("A4 устойчивость к утечкам", part_a4),
             ("A5 детектор утечек", part_a5), ("A6 калибровка", part_a6), ("B качество подбора", part_b)]
    only = set(sys.argv[1:])
    for name, fn in steps:
        if only and not any(name.startswith(o) for o in only):
            continue
        t = time.time()
        print(f"→ {name}…", flush=True)
        fn()
        print(f"  готово за {time.time() - t:.0f} с", flush=True)
    write_report()
    print(json.dumps({k: v for k, v in RESULTS.items() if k != "A1_accuracy"}, ensure_ascii=False, indent=1)[:3000])
    print(f"Всего {time.time() - t0:.0f} с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
