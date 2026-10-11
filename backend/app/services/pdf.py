"""PDF: извлечение текста из резюме и генерация стандартизированного PDF-профиля кандидата."""
from __future__ import annotations

import io
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from pypdf import PdfReader

from app.config import settings
from app.dictionaries import (GRADE_BY_CODE, INDUSTRIES, ROLES, SOFT_SKILLS, SPEC_BY_CODE, WORK_FORMATS,
                              category_label, skill_label)
from app.models import CandidateProfile, utcnow
from app.services.matching import topic_verified

_FONT_CANDIDATES = [
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", None),
    ("/Library/Fonts/Arial Unicode.ttf", None),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
]
PURPLE = (84, 20, 128)
VIOLET = (140, 70, 200)
GREY = (90, 90, 100)


def extract_text(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:10])


def _fonts() -> tuple[str, str]:
    if settings.pdf_font_path and Path(settings.pdf_font_path).exists():
        return settings.pdf_font_path, settings.pdf_font_path
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).exists():
            return regular, bold if bold and Path(bold).exists() else regular
    raise RuntimeError("Не найден TTF-шрифт с кириллицей. Укажите PDF_FONT_PATH или установите fonts-dejavu-core.")


def _t(text: str) -> str:
    """Знак рубля есть не во всех системных шрифтах — пишем «руб.», чтобы PDF выглядел одинаково везде."""
    return text.replace(" ₽", " руб.").replace("₽", "руб.")


class _Doc(FPDF):
    def __init__(self) -> None:
        super().__init__(format="A4")
        regular, bold = _fonts()
        self.add_font("Main", "", regular)
        self.add_font("Main", "B", bold)
        self.set_auto_page_break(True, margin=15)
        self.set_margins(16, 16, 16)

    def footer(self) -> None:
        self.set_y(-12)
        self.set_font("Main", size=8)
        self.set_text_color(*GREY)
        self.cell(0, 6, f"ФСП Талант · сформировано {utcnow():%d.%m.%Y} · стр. {self.page_no()}", align="C")

    def h1(self, text: str) -> None:
        self.set_font("Main", "B", 18)
        self.set_text_color(*PURPLE)
        self.multi_cell(0, 9, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def h2(self, text: str) -> None:
        self.ln(3)
        self.set_font("Main", "B", 12)
        self.set_text_color(*PURPLE)
        self.cell(0, 7, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*VIOLET)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(1.5)

    def p(self, text: str, size: int = 10, color=(30, 30, 40), bold: bool = False) -> None:
        self.set_font("Main", "B" if bold else "", size)
        self.set_text_color(*color)
        self.multi_cell(0, 5.2, _t(text), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def kv(self, key: str, value: str) -> None:
        self.set_font("Main", "B", 10)
        self.set_text_color(*GREY)
        self.cell(48, 5.6, key)
        self.set_font("Main", "", 10)
        self.set_text_color(30, 30, 40)
        self.multi_cell(0, 5.6, _t(value or "—"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _labels(codes: list[str], source: list[dict]) -> str:
    m = {x["code"]: x["label"] for x in source}
    return ", ".join(m.get(c, c) for c in codes) or "—"


def profile_pdf(cand: CandidateProfile, strength: dict, fsp: dict, tasks: list[dict], anonymized: bool) -> bytes:
    """Стандартизированный профиль: одинаковая структура для всех кандидатов, в основе — подтверждённые данные."""
    d = _Doc()
    d.add_page()
    title = f"Кандидат {cand.anon_code}" if anonymized or not cand.full_name else cand.full_name
    d.h1(title)
    cat = category_label(cand.specialization, cand.grade)
    d.p(f"{cat or 'Категория не присвоена'} · стандартизированный профиль ФСП Талант", 11, VIOLET, bold=True)

    d.h2("Категория и подтверждение")
    d.kv("Специализация", SPEC_BY_CODE[cand.specialization]["label"] if cand.specialization else "—")
    if cand.grade:
        d.kv("Грейд", f"{GRADE_BY_CODE[cand.grade]['label']} — подтверждён адаптивным тестом"
                      + (f" {cand.grade_changed_at:%d.%m.%Y}" if cand.grade_changed_at else ""))
        d.kv("Оценка уровня θ", f"{cand.theta:.2f} ± {cand.theta_se:.2f}" if cand.theta is not None else "—")
    else:
        d.kv("Грейд", "не подтверждён")
    d.kv("Сила профиля", f"{round(strength['P'] * 100)} / 100  (тест {round(strength['T'] * 100)}, "
                         f"ФСП {round(strength['F'] * 100)}, активность {round(strength['A'] * 100)})")

    if not anonymized:
        d.h2("Контакты")
        d.kv("Email", cand.contact_email or cand.user.email)
        d.kv("Телефон", cand.phone)
        d.kv("Telegram", cand.telegram)

    d.h2("Навыки")
    verified = [t for t, r in (cand.verified_topics or {}).items() if topic_verified(r)]
    d.kv("Подтверждено тестом", ", ".join(skill_label(s) for s in verified) or "—")
    d.kv("Заявленный стек", ", ".join(skill_label(s) for s in cand.stack or []))
    d.kv("Роли", _labels(cand.roles or [], ROLES))
    d.kv("Софт-скиллы", _labels(cand.soft_skills or [], SOFT_SKILLS))

    d.h2("Опыт и условия")
    d.kv("Стаж", f"{cand.experience_years:g} лет" if cand.experience_years else "—")
    d.kv("Отрасли", _labels(cand.industries or [], INDUSTRIES))
    d.kv("Формат", _labels(cand.work_format or [], WORK_FORMATS))
    d.kv("Город", (cand.city or "—") + (", готов к переезду" if cand.relocation else ""))
    if not anonymized or (cand.privacy or {}).get("show_salary", True):
        d.kv("Ожидания", f"от {cand.salary_expect_min:,} ₽/мес".replace(",", " ") if cand.salary_expect_min else "—")
    if cand.about:
        d.kv("О себе", cand.about)

    d.h2("Достижения ФСП")
    if fsp.get("achievements"):
        for a in fsp["achievements"]:
            d.p(f"• {a['headline']}", 10)
            d.p(f"   {a.get('discipline_label', '')}" + (f" · команда «{a['team_name']}»" if a.get("team_name") else ""), 9, GREY)
    else:
        d.p(fsp.get("status_text") or "Нет данных ФСП", 10, GREY)

    d.h2("Регулярные задания")
    if tasks:
        for t in tasks:
            sc = f"автооценка {round((t['auto_score'] or 0) * 100)}%" + (f", оценка работодателя {t['employer_score']}/5" if t.get("employer_score") else "")
            d.p(f"• {t['title']} — {sc}", 10)
    else:
        d.p("Пока нет решённых заданий", 10, GREY)

    d.ln(4)
    d.p("Категория присвоена по результатам адаптивного теста на параметрических заданиях (IRT 2PL), а не по самоописанию. "
        "Достижения получены из реестра ФСП по привязке ФСП ID.", 8, GREY)
    return bytes(d.output())


def make_sample_resume(path: Path) -> None:
    """Пример резюме для демонстрации автораспознавания PDF."""
    d = _Doc()
    d.add_page()
    d.h1("Смирнов Алексей Викторович")
    d.p("Backend-разработчик (Python)", 12, VIOLET, bold=True)
    d.p("Email: a.smirnov.dev@example.com · Телефон: +7 (916) 123-45-67 · Telegram: @asmirnov_dev")
    d.p("Город: Казань · Готов к удалённой работе")
    d.h2("О себе")
    d.p("Разрабатываю высоконагруженные сервисы на Python. Люблю чистую архитектуру, ревью кода и наставничество. "
        "Призёр командного чемпионата по продуктовому программированию.")
    d.h2("Опыт работы")
    d.p("03.2021 — н.в. · ООО «Северный код», Python-разработчик", bold=True)
    d.p("Микросервисы на FastAPI и Django, PostgreSQL, Redis, Kafka. Перевёл сервис отчётов на асинхронную обработку, "
        "сократив время ответа в 4 раза. Настроил CI/CD в GitLab CI, контейнеризация в Docker, деплой в Kubernetes.")
    d.p("09.2019 — 02.2021 · Студия «Пиксель», младший разработчик", bold=True)
    d.p("REST API для мобильных приложений, интеграции с платёжными системами, покрытие тестами на pytest.")
    d.h2("Навыки")
    d.p("Python, FastAPI, Django, SQL, PostgreSQL, Redis, Kafka, Docker, Kubernetes, Git, Linux, REST API, "
        "микросервисы, асинхронность (asyncio), паттерны проектирования")
    d.h2("Личные качества")
    d.p("Ответственность, работа в команде, наставничество, самоорганизация, коммуникабельность.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(d.output()))
