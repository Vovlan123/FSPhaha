"""Item Response Theory, модель 2PL.

P(верно | θ) = 1 / (1 + exp(-a·(θ − b)))
  θ — уровень кандидата (шкала N(0,1) популяции), a — различающая способность шаблона, b — его сложность.

Оценка θ — EAP (апостериорное среднее) на равномерной сетке с нормальным априорным распределением.
EAP устойчива при малом числе ответов и при «все верно / все неверно», где ML-оценка уходит в бесконечность.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

GRID = np.linspace(-4.0, 4.0, 81)
PRIOR_SD = 1.5
_LOG_PRIOR = -0.5 * (GRID / PRIOR_SD) ** 2


def p_correct(theta: float | np.ndarray, a: float, b: float) -> float | np.ndarray:
    return 1.0 / (1.0 + np.exp(-a * (theta - b)))


def fisher_info(theta: float, a: float, b: float) -> float:
    p = float(p_correct(theta, a, b))
    return a * a * p * (1.0 - p)


def eap(responses: Sequence[tuple[float, float, int]], prior_mean: float = 0.0) -> tuple[float, float]:
    """Оценка θ и её стандартной ошибки по ответам [(a, b, u)], u ∈ {0, 1}."""
    log_post = _LOG_PRIOR.copy() if prior_mean == 0.0 else -0.5 * ((GRID - prior_mean) / PRIOR_SD) ** 2
    for a, b, u in responses:
        p = p_correct(GRID, a, b)
        p = np.clip(p, 1e-9, 1 - 1e-9)
        log_post += np.log(p) if u else np.log(1.0 - p)
    log_post -= log_post.max()
    w = np.exp(log_post)
    w /= w.sum()
    mean = float((GRID * w).sum())
    sd = float(math.sqrt(max(((GRID - mean) ** 2 * w).sum(), 1e-12)))
    return mean, sd


def simulate_answer(theta: float, a: float, b: float, rng: np.random.Generator) -> int:
    return int(rng.random() < p_correct(theta, a, b))


def calibrate_2pl(resp: np.ndarray, n_iter: int = 40) -> tuple[np.ndarray, np.ndarray]:
    """Калибровка параметров a, b по матрице ответов (люди × шаблоны, NaN = шаблон не показывался).

    Маргинальное максимальное правдоподобие, EM-алгоритм Бока–Эйткина на квадратурной сетке:
      E-шаг: апостериорное распределение θ каждого человека на сетке при текущих параметрах;
      M-шаг: для каждого шаблона — взвешенная логистическая регрессия «ожидаемые верные / ожидаемые показы»
             по узлам сетки (Ньютон–Рафсон по (a, c), где c = −a·b).
    Используется в валидации: восстанавливаем параметры по смоделированным ответам и сравниваем с истинными.
    """
    n_people, n_items = resp.shape
    grid = np.linspace(-4, 4, 41)
    log_prior = -0.5 * grid**2
    mask = ~np.isnan(resp)
    u = np.nan_to_num(resp)
    a = np.ones(n_items)
    c = np.zeros(n_items)  # c = −a·b
    for _ in range(n_iter):
        # E-шаг
        logits = np.outer(grid, a) + c  # (Q, I)
        logp = -np.logaddexp(0, -logits)
        logq = -np.logaddexp(0, logits)
        ll = (u[:, None, :] * logp[None] + (1 - u[:, None, :]) * logq[None]) * mask[:, None, :]  # (N, Q, I)
        post = ll.sum(axis=2) + log_prior[None, :]
        post -= post.max(axis=1, keepdims=True)
        post = np.exp(post)
        post /= post.sum(axis=1, keepdims=True)  # (N, Q)
        n_k = post.T @ mask  # ожидаемое число показов шаблона в узле (Q, I)
        r_k = post.T @ (u * mask)  # ожидаемое число верных (Q, I)
        # M-шаг: несколько итераций Ньютона для каждого шаблона одновременно
        for _ in range(5):
            z = np.outer(grid, a) + c
            p = 1 / (1 + np.exp(-z))
            g_c = (r_k - n_k * p).sum(axis=0)
            g_a = ((r_k - n_k * p) * grid[:, None]).sum(axis=0)
            w = n_k * p * (1 - p)
            h_cc = -(w).sum(axis=0) - 1e-6
            h_aa = -(w * grid[:, None] ** 2).sum(axis=0) - 1e-6
            h_ac = -(w * grid[:, None]).sum(axis=0)
            det = h_aa * h_cc - h_ac**2
            det = np.where(np.abs(det) < 1e-9, -1e-9, det)
            da = (h_cc * g_a - h_ac * g_c) / det
            dc = (h_aa * g_c - h_ac * g_a) / det
            a = np.clip(a - da, 0.2, 4.0)
            c = np.clip(c - dc, -12, 12)
    b = -c / a
    return a, b
