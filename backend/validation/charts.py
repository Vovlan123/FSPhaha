"""Простые SVG-графики для отчёта валидации (без внешних библиотек).

Один акцентный цвет — на нашей механике, остальные столбцы серые; заголовок формулирует вывод с числом,
опорная линия (например, «без утечки») подписана прямо на графике. SVG корректно показывается на GitHub и в PDF.
"""
from __future__ import annotations

from html import escape
from pathlib import Path

ACCENT, GREY, TEXT, MUTED, GRID, REF = "#5b1a8c", "#cfc6db", "#1d1428", "#6b5c7b", "#ece6f3", "#b3261e"
FONT = "Manrope, 'Segoe UI', Arial, sans-serif"


def bar_chart(path: Path, title: str, subtitle: str, rows: list[dict], *, xmax: float, fmt, ref: dict | None = None,
              source: str = "") -> None:
    """Горизонтальные столбцы. rows: {label, value, accent?, lo?, hi?}; ref: {value, label} — вертикальная опорная линия."""
    left, width, bar_h, gap, top = 300, 380, 26, 18, 84
    height = top + len(rows) * (bar_h + gap) + 46
    x = lambda v: left + v / xmax * width  # noqa: E731
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 760 {height}" width="760" height="{height}" '
           f'font-family="{FONT}" role="img" aria-label="{escape(title)}">',
           f'<rect width="760" height="{height}" fill="#ffffff"/>',
           f'<text x="20" y="32" font-size="17" font-weight="700" fill="{TEXT}">{escape(title)}</text>',
           f'<text x="20" y="54" font-size="12.5" fill="{MUTED}">{escape(subtitle)}</text>']
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        gx = x(t * xmax)
        out.append(f'<line x1="{gx:.1f}" y1="{top - 8}" x2="{gx:.1f}" y2="{height - 40}" stroke="{GRID}"/>')
        out.append(f'<text x="{gx:.1f}" y="{height - 24}" font-size="11" fill="{MUTED}" text-anchor="middle">{escape(fmt(t * xmax))}</text>')
    for i, r in enumerate(rows):
        y = top + i * (bar_h + gap)
        color = ACCENT if r.get("accent") else GREY
        weight = "700" if r.get("accent") else "500"
        out.append(f'<text x="{left - 12}" y="{y + bar_h / 2 + 4.5:.1f}" font-size="13" font-weight="{weight}" fill="{TEXT}" '
                   f'text-anchor="end">{escape(r["label"])}</text>')
        out.append(f'<rect x="{left}" y="{y}" width="{max(x(r["value"]) - left, 1.5):.1f}" height="{bar_h}" rx="4" fill="{color}"/>')
        end = x(r["value"])
        if r.get("lo") is not None and r.get("hi") is not None:
            lo, hi = x(r["lo"]), x(r["hi"])
            cy = y + bar_h / 2
            out.append(f'<line x1="{lo:.1f}" y1="{cy}" x2="{hi:.1f}" y2="{cy}" stroke="{TEXT}" stroke-width="1.4"/>')
            out.append(f'<line x1="{lo:.1f}" y1="{cy - 6}" x2="{lo:.1f}" y2="{cy + 6}" stroke="{TEXT}" stroke-width="1.4"/>')
            out.append(f'<line x1="{hi:.1f}" y1="{cy - 6}" x2="{hi:.1f}" y2="{cy + 6}" stroke="{TEXT}" stroke-width="1.4"/>')
            end = max(end, hi)
        label_x = end + 8
        if ref and abs(x(ref["value"]) - label_x) < 36:  # подпись не должна лежать на опорной линии
            label_x = x(ref["value"]) + 8
        out.append(f'<text x="{label_x:.1f}" y="{y + bar_h / 2 + 4.5:.1f}" font-size="13" font-weight="{weight}" '
                   f'fill="{ACCENT if r.get("accent") else TEXT}">{escape(fmt(r["value"]))}</text>')
    if ref:
        rx = x(ref["value"])
        out.append(f'<line x1="{rx:.1f}" y1="{top - 14}" x2="{rx:.1f}" y2="{height - 40}" stroke="{REF}" stroke-width="1.5" stroke-dasharray="4 3"/>')
        out.append(f'<text x="{rx + 5:.1f}" y="{top - 16}" font-size="11.5" fill="{REF}">{escape(ref["label"])}</text>')
    if source:
        out.append(f'<text x="740" y="{height - 6}" font-size="10.5" fill="{MUTED}" text-anchor="end">{escape(source)}</text>')
    out.append("</svg>")
    path.write_text("\n".join(out), encoding="utf-8")


def pct(v: float) -> str:
    return f"{round(v * 100)}%"


def dec2(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")
