"""Инфраструктура банка параметрических шаблонов заданий.

Шаблон — это генератор: из зерна (seed) он детерминированно строит уникальный экземпляр задания
(меняются числа, имена, порядок строк кода и вариантов). Сложность и различающая способность (параметры
IRT 2PL `a`, `b`) закреплены за шаблоном, а не за экземпляром: все экземпляры одного шаблона проверяют одно
и то же умение одинаковой трудности. Поэтому:
  * слитый ответ на конкретный экземпляр бесполезен — другой кандидат получит другой экземпляр;
  * результаты разных кандидатов сравнимы, потому что оценка θ считается по параметрам шаблонов.

Контракт генератора: функция `gen(rng: random.Random) -> dict` с ключами
  stem        — текст вопроса (рус.), обязателен;
  correct     — верный ответ (str), обязателен;
  distractors — список неверных ответов (str), минимум 3 уникальных и отличных от correct;
  code        — фрагмент кода/конфига к вопросу (str), необязателен;
  code_lang   — язык подсветки: python | javascript | typescript | sql | bash | yaml | dockerfile | text | ...;
  explanation — краткое пояснение верного ответа (показывается в отчётах, не кандидату во время теста).
Для шаблонов формата `output` на Python можно передать `verify=True`: самопроверка выполнит `code`
и сравнит stdout с `correct`.
"""
from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field

POOLS = ("core", "backend", "frontend", "data", "devops", "qa")
FORMATS = ("output", "bug", "concept", "calc")


@dataclass
class ItemInstance:
    template_id: str
    seed: int
    stem: str
    options: list[str]
    correct_index: int
    code: str | None = None
    code_lang: str | None = None
    explanation: str = ""

    def public_payload(self) -> dict:
        """То, что уходит клиенту: без верного ответа и пояснения."""
        return {"stem": self.stem, "code": self.code, "code_lang": self.code_lang, "options": self.options}

    def stored_payload(self) -> dict:
        return {**self.public_payload(), "explanation": self.explanation}


@dataclass
class Template:
    id: str
    pool: str
    topics: list[str]
    fmt: str
    a: float
    b: float
    title: str
    generator: Callable[[random.Random], dict]
    variants: int = 100  # оценка числа различимых экземпляров (для документации и проверки)
    verify: bool = False
    extra: dict = field(default_factory=dict)

    def generate(self, seed: int) -> ItemInstance:
        rng = random.Random(f"{self.id}:{seed}")
        raw = self.generator(rng)
        correct = str(raw["correct"]).strip()
        seen = {correct}
        distractors: list[str] = []
        for d in raw["distractors"]:
            d = str(d).strip()
            if d and d not in seen:
                seen.add(d)
                distractors.append(d)
            if len(distractors) == 3:
                break
        if len(distractors) < 3:
            raise ValueError(f"{self.id}: меньше 3 уникальных дистракторов при seed={seed}")
        options = [correct, *distractors]
        rng.shuffle(options)
        return ItemInstance(
            template_id=self.id,
            seed=seed,
            stem=raw["stem"],
            options=options,
            correct_index=options.index(correct),
            code=raw.get("code"),
            code_lang=raw.get("code_lang"),
            explanation=raw.get("explanation", ""),
        )


REGISTRY: dict[str, Template] = {}


def template(*, id: str, pool: str, topics: list[str], fmt: str, a: float, b: float, title: str,
             variants: int = 100, verify: bool = False):
    """Декоратор регистрации шаблона. Пример:

    @template(id="core.py_slice", pool="core", topics=["python"], fmt="output", a=1.2, b=-1.0,
              title="Срез списка в Python", variants=500, verify=True)
    def gen(rng): ...
    """
    if pool not in POOLS:
        raise ValueError(f"Неизвестный пул {pool}")
    if fmt not in FORMATS:
        raise ValueError(f"Неизвестный формат {fmt}")

    def deco(fn: Callable[[random.Random], dict]) -> Callable[[random.Random], dict]:
        if id in REGISTRY:
            raise ValueError(f"Шаблон {id} уже зарегистрирован")
        REGISTRY[id] = Template(id=id, pool=pool, topics=topics, fmt=fmt, a=a, b=b, title=title,
                                generator=fn, variants=variants, verify=verify)
        return fn

    return deco
