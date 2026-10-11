"""Сборка PDF сопроводительной документации: `python docs/build_pdf.py` из корня репозитория.

docs/documentation.md + приложение docs/validation/report.md (с графиками) → docs/documentation.pdf.
Нужны пакет `markdown-it-py` (pip install markdown-it-py) и Google Chrome или Chromium (печать в PDF без окна).
Используется CommonMark-разбор — как на GitHub, поэтому вложенные списки с отступом в 2 пробела работают.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

from markdown_it import MarkdownIt

DOCS = Path(__file__).resolve().parent
CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "", shutil.which("chromium") or "", shutil.which("chromium-browser") or "",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
]

CSS = """
@page { size: A4; margin: 18mm 16mm 18mm 16mm; }
@page :first { margin: 0; }
* { box-sizing: border-box; }
body { font-family: 'Manrope', 'Segoe UI', Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1d1428; }
h1 { font-size: 22pt; color: #4b0f73; margin: 0 0 6pt; }
h2 { font-size: 15pt; color: #4b0f73; margin: 22pt 0 8pt; padding-bottom: 4pt; border-bottom: 2px solid #d9c4ef; page-break-after: avoid; }
h3 { font-size: 12pt; color: #3d0c63; margin: 14pt 0 6pt; page-break-after: avoid; }
p, li { margin: 0 0 5pt; }
a { color: #5b1a8c; text-decoration: none; }
code { font-family: 'JetBrains Mono', Menlo, monospace; font-size: 8.8pt; background: #f3eef9; padding: 0 3px; border-radius: 3px; }
pre { background: #1c1229; color: #efe7fb; padding: 9pt 11pt; border-radius: 6px; font-size: 7.6pt; line-height: 1.45;
      white-space: pre; overflow: hidden; page-break-inside: avoid; font-variant-ligatures: none; }
pre code { background: none; color: inherit; padding: 0; }
table { border-collapse: collapse; width: 100%; margin: 6pt 0 10pt; font-size: 9pt; page-break-inside: avoid; }
th { background: #f3eef9; color: #3d0c63; text-align: left; font-weight: 700; }
th, td { border: 1px solid #e4daee; padding: 4pt 6pt; vertical-align: top; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; background: #fff4d6; border-left: 3px solid #e3b341; border-radius: 4px; }
img { max-width: 100%; display: block; margin: 8pt auto; page-break-inside: avoid; }
li > p { margin: 0 0 3pt; }
ul, ol { padding-left: 18pt; margin: 0 0 6pt; }
hr { border: 0; border-top: 1px solid #e4daee; margin: 14pt 0; }
.cover { height: 296mm; display: flex; flex-direction: column; justify-content: space-between; page-break-after: always;
         background: linear-gradient(150deg, #2a0845, #5b1a8c 65%, #8a3fc4); color: #fff; padding: 26mm 20mm; margin: 0;
         -webkit-print-color-adjust: exact; print-color-adjust: exact; }
.cover h1 { color: #fff; font-size: 30pt; line-height: 1.15; }
.cover .sub { font-size: 13pt; opacity: .9; max-width: 140mm; }
.cover .meta { font-size: 10pt; opacity: .8; }
.cover .logo { font-weight: 800; letter-spacing: .5px; font-size: 12pt; }
.appendix { page-break-before: always; }
"""


_MD = MarkdownIt("commonmark", {"html": True}).enable("table")


def md_to_html(text: str) -> str:
    return _MD.render(text)


def build() -> Path:
    doc = (DOCS / "documentation.md").read_text(encoding="utf-8")
    report = (DOCS / "validation" / "report.md").read_text(encoding="utf-8")
    # Картинки отчёта лежат рядом с ним — переписываем пути относительно docs/
    report = re.sub(r"\]\((chart_[a-z_]+\.svg)\)", r"](validation/\1)", report)
    report = report.replace("# Валидация решения «ФСП Талант»", "# Приложение. Отчёт валидации", 1)
    body = md_to_html(doc.split("\n", 1)[1])  # заголовок документа — на обложке
    appendix = md_to_html(report)
    html = f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=JetBrains+Mono&display=swap" rel="stylesheet">
<title>ФСП Талант — сопроводительная документация</title><style>{CSS}</style></head><body>
<section class="cover">
  <div class="logo">ФСП Талант · Федерация спортивного программирования</div>
  <div>
    <h1>Сопроводительная документация</h1>
    <div class="sub">Цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений участника ФСП:
    обратная механика подбора, адаптивное тестирование на параметрических заданиях, интеграция с ФСП ID.</div>
  </div>
  <div class="meta">Архитектура · механики тестирования и подбора · валидация · интеграция с ФСП · API · запуск</div>
</section>
{body}
<section class="appendix">{appendix}</section>
</body></html>"""
    out_html = DOCS / "documentation.html"
    out_html.write_text(html, encoding="utf-8")
    chrome = next((c for c in CHROME_CANDIDATES if c and Path(c).exists()), None)
    if not chrome:
        sys.exit("Не найден Chrome/Chromium для печати в PDF; HTML сохранён в docs/documentation.html")
    out_pdf = DOCS / "documentation.pdf"
    subprocess.run([chrome, "--headless=new", "--no-proxy-server", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={out_pdf}", "--virtual-time-budget=8000", out_html.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out_html.unlink()
    return out_pdf


if __name__ == "__main__":
    print(build())
