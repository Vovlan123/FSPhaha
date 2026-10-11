"""Разбор свободного текста: описание потребности работодателя и PDF-резюме кандидата.

Подход без внешних моделей (запускается офлайн и детерминирован):
  * словарь навыков с синонимами и русскими формами (dictionaries.SKILLS) → канонические навыки;
  * правила для грейда, формата работы, зарплатной вилки, стажа, контактов;
  * TF-IDF по усечённым основам слов (лёгкий стемминг для русского) — для близости текстов.
Это место расширения: в продуктиве разбор можно усилить LLM, сохранив тот же формат результата.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from datetime import date

from app.dictionaries import (GRADE_KEYWORDS, ROLES, SKILLS, SOFT_SKILLS, SPEC_BY_CODE, SPEC_CODES, SPEC_KEYWORDS,
                              WORK_FORMATS)

_FLAGS = re.IGNORECASE | re.UNICODE


def _compile(patterns: list[str]) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns), _FLAGS)


_SKILL_RE = {code: _compile(s["re"]) for code, s in SKILLS.items()}
_SPEC_RE = {code: _compile(p) for code, p in SPEC_KEYWORDS.items()}
_GRADE_RE = {code: _compile(p) for code, p in GRADE_KEYWORDS.items()}
_FORMAT_RE = {w["code"]: _compile(w["re"]) for w in WORK_FORMATS}
_SOFT_RE = {s["code"]: _compile(s["re"]) for s in SOFT_SKILLS}
_ROLE_RE = {r["code"]: _compile(r["re"]) for r in ROLES}
_NICE_MARKERS = re.compile(r"будет плюсом|плюсом будет|желательн\w*|nice to have|приветству\w*|как преимущество|дополнительн\w* плюс", _FLAGS)


def extract_skills(text: str) -> list[str]:
    """Канонические навыки, упомянутые в тексте, в порядке первого упоминания."""
    found: list[tuple[int, str]] = []
    for code, rx in _SKILL_RE.items():
        m = rx.search(text)
        if m:
            found.append((m.start(), code))
    return [c for _, c in sorted(found)]


def _sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?;\n])\s+|\n+|•|·|—\s", text) if s.strip()]


def detect_specialization(text: str, skills: list[str]) -> tuple[str | None, dict[str, float]]:
    """Специализация по ключевым словам (вес 3) и голосованию навыков (вес 1/число специализаций навыка)."""
    scores = {c: 0.0 for c in SPEC_CODES}
    for code, rx in _SPEC_RE.items():
        scores[code] += 3.0 * len(rx.findall(text))
    for sk in skills:
        specs = [s for s in SPEC_CODES if sk in SPEC_BY_CODE[s]["skills"]]
        for s in specs:
            scores[s] += 1.0 / len(specs)
    best = max(scores, key=scores.get)
    return (best if scores[best] > 0 else None), scores


def years_to_grade(years: float) -> str:
    if years < 0.5:
        return "intern"
    if years < 1.5:
        return "junior"
    if years < 4:
        return "middle"
    return "senior"




def detect_grade(text: str) -> tuple[str | None, str]:
    """Грейд по явным словам (senior/мидл/…), иначе по требуемому опыту «от N лет»."""
    for code in ("senior", "middle", "junior", "intern"):
        if _GRADE_RE[code].search(text):
            return code, "keyword"
    m = re.search(r"опыт\w*[^.\n]{0,60}?(\d+(?:[.,]\d+)?)\s*\+?\s*(?:год|года|лет)", text, _FLAGS)
    if m:
        return years_to_grade(float(m.group(1).replace(",", "."))), "experience"
    return None, "none"


def detect_formats(text: str) -> list[str]:
    return [code for code, rx in _FORMAT_RE.items() if rx.search(text)]


def _num(s: str, mult_hint: str) -> int:
    v = float(s.replace(" ", "").replace(" ", "").replace(",", "."))
    if mult_hint and mult_hint.lower() in {"к", "k", "тыс", "тыс."}:
        v *= 1000
    elif v < 1000:  # «200–300» без единиц в контексте зарплаты почти всегда тысячи
        v *= 1000
    return int(round(v))


_SALARY_RANGE = re.compile(
    r"(?:от\s*)?(\d[\d\s ]{1,9}(?:[.,]\d+)?)\s*(к|k|тыс\.?)?\s*(?:₽|руб\.?|р\.)?\s*(?:до|-|–|—)\s*(\d[\d\s ]{1,9}(?:[.,]\d+)?)\s*(к|k|тыс\.?)?\s*(?:₽|руб|р\.|rub)",
    _FLAGS)
_SALARY_RANGE_LOOSE = re.compile(
    r"(?:зарплат\w*|оклад\w*|вилк\w*|доход\w*|з/п|зп)[^\d\n]{0,20}(?:от\s*)?(\d[\d\s ]{1,9})\s*(к|k|тыс\.?)?\s*(?:₽|руб\.?)?\s*(?:до|-|–|—)\s*(\d[\d\s ]{1,9})\s*(к|k|тыс\.?)?",
    _FLAGS)


def detect_salary(text: str) -> tuple[int | None, int | None]:
    m = _SALARY_RANGE.search(text) or _SALARY_RANGE_LOOSE.search(text)
    if not m:
        return None, None
    hint = m.group(2) or m.group(4) or ""
    lo, hi = _num(m.group(1), m.group(2) or hint), _num(m.group(3), m.group(4) or hint)
    if lo > hi:
        lo, hi = hi, lo
    if not (10_000 <= lo <= 5_000_000):
        return None, None
    return lo, hi


def parse_need(text: str) -> dict:
    """Описание потребности → структура для формы. Навыки из предложений с маркерами «будет плюсом»
    идут в желательный стек, остальные — в обязательный."""
    must: list[str] = []
    nice: list[str] = []
    for sent in _sentences(text):
        target = nice if _NICE_MARKERS.search(sent) else must
        for sk in extract_skills(sent):
            if sk not in must and sk not in nice:
                target.append(sk)
    all_skills = must + nice
    spec, spec_scores = detect_specialization(text, all_skills)
    grade, grade_source = detect_grade(text)
    sal_from, sal_to = detect_salary(text)
    # Навыки чужой специализации оставляем: работодателю виднее, но подсвечиваем во фронтенде
    return {
        "specialization": spec,
        "specialization_scores": spec_scores,
        "grade": grade,
        "grade_source": grade_source,
        "stack_must": must,
        "stack_nice": nice,
        "work_format": detect_formats(text),
        "salary_from": sal_from,
        "salary_to": sal_to,
    }


# ---------------------------------------------------------------- резюме

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+7|8)[\s(-]*\d{3}[\s)-]*\d{3}[\s-]*\d{2}[\s-]*\d{2}")
_TG_RE = re.compile(r"(?:t\.me/|telegram[:\s]*@?|tg[:\s]*@?|(?<![\w.])@)([A-Za-z][A-Za-z0-9_]{4,31})\b", _FLAGS)
_NAME_RE = re.compile(r"^\s*([А-ЯЁ][а-яё]+(?:-[А-ЯЁ][а-яё]+)?)\s+([А-ЯЁ][а-яё]+)(?:\s+([А-ЯЁ][а-яё]+))?\s*$", re.M)
_CITY_RE = re.compile(r"(?:город|г\.|проживание|локация|location)[:\s]+([А-ЯЁA-Z][а-яёa-z-]+(?:[\s-][А-ЯЁA-Z][а-яёa-z-]+)?)", _FLAGS)
_RANGE_RE = re.compile(r"(?:(\d{2})[./])?((?:19|20)\d{2})\s*(?:-|–|—|по)\s*(?:(\d{2})[./])?((?:19|20)\d{2}|н\.?\s?в\.?|настоящее время|наст\.?\s*время|сейчас|present|now)", _FLAGS)


def _experience_years(text: str, today: date | None = None) -> float | None:
    """Стаж: явное «опыт работы N лет» или сумма периодов «2019 — 2022 / 03.2022 — н.в.» (с объединением пересечений)."""
    today = today or date.today()
    m = re.search(r"опыт\w*\s*(?:работы|коммерческой разработки)?[^\d\n]{0,20}(\d+(?:[.,]\d+)?)\s*(?:год|года|лет)(?:\s*(\d+)\s*мес)?", text, _FLAGS)
    if m:
        years = float(m.group(1).replace(",", "."))
        if m.group(2):
            years += int(m.group(2)) / 12
        return round(years, 1)
    spans = []
    for mm in _RANGE_RE.finditer(text):
        m1 = int(mm.group(1)) if mm.group(1) else 1
        y1 = int(mm.group(2))
        if mm.group(4)[:1].isdigit():
            y2, m2 = int(mm.group(4)), int(mm.group(3)) if mm.group(3) else 12
        else:
            y2, m2 = today.year, today.month
        start, end = y1 * 12 + m1, y2 * 12 + m2
        if 1990 * 12 <= start <= end <= (today.year + 1) * 12:
            spans.append((start, end))
    if not spans:
        return None
    spans.sort()
    total, cur_s, cur_e = 0, *spans[0]
    for s, e in spans[1:]:
        if s <= cur_e:
            cur_e = max(cur_e, e)
        else:
            total += cur_e - cur_s
            cur_s, cur_e = s, e
    total += cur_e - cur_s
    return round(total / 12, 1)


def parse_resume(text: str) -> dict:
    """Текст резюме → поля профиля. Возвращает и «уверенность» по каждому полю, чтобы фронтенд
    подсветил то, что стоит проверить вручную."""
    text_norm = text.replace(" ", " ")
    name = None
    for m in _NAME_RE.finditer(text_norm[:600]):
        cand = " ".join(x for x in m.groups() if x)
        if not re.search(r"резюме|разработчик|инженер|контакт|опыт|навык", cand, _FLAGS):
            name = cand
            break
    email = (_EMAIL_RE.search(text_norm) or [None])[0] if _EMAIL_RE.search(text_norm) else None
    phone_m = _PHONE_RE.search(text_norm)
    tg_m = None
    for m in _TG_RE.finditer(text_norm):
        if email and m.group(1).lower() in email.lower():
            continue
        tg_m = m
        break
    city_m = _CITY_RE.search(text_norm)
    skills = extract_skills(text_norm)
    spec, _ = detect_specialization(text_norm, skills)
    years = _experience_years(text_norm)
    # В резюме слова «младший/старший» часто относятся к прошлым должностям, поэтому стаж надёжнее
    grade = years_to_grade(years) if years is not None else detect_grade(text_norm)[0]
    return {
        "full_name": name,
        "contact_email": email,
        "phone": re.sub(r"[^\d+]", "", phone_m.group(0)) if phone_m else None,
        "telegram": "@" + tg_m.group(1) if tg_m else None,
        "city": city_m.group(1) if city_m else None,
        "specialization": spec,
        "stack": skills,
        "experience_years": years,
        "grade_guess": grade,
        "roles": [code for code, rx in _ROLE_RE.items() if rx.search(text_norm)],
        "soft_skills": [code for code, rx in _SOFT_RE.items() if rx.search(text_norm)],
        "about": _about_snippet(text_norm),
    }


_SECTION_RE = re.compile(r"\n\s*(?:опыт работы|опыт|навыки|ключевые навыки|образование|личные качества|контакты|"
                         r"experience|skills|education)\b", _FLAGS)


def _about_snippet(text: str) -> str:
    """Текст раздела «О себе» до следующего заголовка раздела (не длиннее 600 символов)."""
    m = re.search(r"(?:о себе|about me|обо мне)[:\s]*", text, _FLAGS)
    if not m:
        return ""
    rest = text[m.end():m.end() + 1500]
    end = _SECTION_RE.search(rest)
    return re.sub(r"\s+", " ", rest[:end.start()] if end else rest).strip()[:600]


# ---------------------------------------------------------------- TF-IDF

_TOKEN_RE = re.compile(r"[a-zа-яё0-9+#]+", _FLAGS)
_STOP = set("и в во не что он на я с со как а то все она так его но да ты к у же вы за бы по только ее мне было вот от "
            "меня еще нет о из ему теперь когда даже ну вдруг ли если уже или ни быть был него до вас нибудь опять уж "
            "вам ведь там потом себя ничего ей может они тут где есть надо ней для мы тебя их чем была сам чтобы без "
            "будто чего раз тоже себе под будет ж тогда кто этот того потому этого какой совсем ним здесь этом один "
            "почти мой тем чтобы нее сейчас были куда зачем всех никогда можно при наконец два об другой хоть после "
            "над больше тот через эти нас про всего них какая много разве три эту моя впрочем хорошо свою этой перед "
            "иногда лучше чуть том нельзя такой им более всегда конечно всю между the and of to in for with on at".split())


def _stem(tok: str) -> str:
    return tok[:6] if len(tok) > 6 and re.match(r"[а-яё]", tok) else tok


def tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower()) if t not in _STOP and len(t) > 1]


class TfIdf:
    """Мини-TF-IDF по корпусу документов (кандидаты), косинусная близость с запросом (потребность)."""

    def __init__(self, docs: list[str]):
        self.n = max(len(docs), 1)
        df: Counter = Counter()
        for d in docs:
            df.update(set(tokens(d)))
        self.idf = {t: math.log((1 + self.n) / (1 + c)) + 1 for t, c in df.items()}

    def vec(self, text: str) -> dict[str, float]:
        tf = Counter(tokens(text))
        v = {t: (1 + math.log(c)) * self.idf.get(t, math.log(1 + self.n) + 1) for t, c in tf.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    @staticmethod
    def cosine(a: dict[str, float], b: dict[str, float]) -> float:
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(t, 0.0) for t, x in a.items())
