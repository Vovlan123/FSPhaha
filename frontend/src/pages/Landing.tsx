import { Link } from "react-router-dom";
import { Logo } from "../components/Layout";

const FEATURES = [
  { icon: "◎", title: "Категория вместо резюме", text: "Работодатель видит не самоописание, а категорию «специализация × грейд», подтверждённую адаптивным тестом." },
  { icon: "⟳", title: "Тест, который нельзя «слить»", text: "Каждый получает свой экземпляр задания из параметрического шаблона, а сложность и оценка сравнимы благодаря IRT." },
  { icon: "➜", title: "Инициатива у работодателя", text: "Компания находит нужную категорию, видит, почему кандидат в подборке, и сама отправляет приглашение." },
  { icon: "₽", title: "Зарплата видна сразу", text: "Вилка «от–до» обязательна в каждом приглашении и вакансии: кандидат знает условия до начала общения." },
  { icon: "★", title: "Достижения ФСП", text: "Результаты соревнований подтягиваются по ФСП ID и поднимают кандидата внутри категории." },
  { icon: "🔒", title: "Контакты под контролем", text: "Профиль анонимен: контакты открываются, только когда кандидат принял приглашение или откликнулся сам." },
];

export default function Landing() {
  return (
    <>
      <section className="landing-hero">
        <div className="inner stack-lg">
          <div className="row-between">
            <Logo />
            <div className="row">
              <Link to="/how-it-works" className="btn btn-light btn-sm">Как это работает</Link>
              <Link to="/login" className="btn btn-white btn-sm">Войти</Link>
            </div>
          </div>
          <div className="hero-split">
          <div className="stack-lg">
            <span className="eyebrow">Подбор с подтверждённым профилем</span>
            <h1>Подбор ИТ-специалистов, где квалификацию подтверждает тест и ФСП, а не резюме</h1>
            <p className="lead">
              Кандидат проходит опрос и адаптивный тест и попадает в категорию. Работодатель описывает потребность,
              получает объяснённую подборку и сам приглашает нужного человека с зарплатной вилкой.
            </p>
          </div>
          <div className="hero-glass" aria-label="Пример карточки категории">
            <div className="k">Пример категории</div>
            <div className="big">Backend · Middle</div>
            <div className="small" style={{ opacity: 0.8 }}>Python · PostgreSQL · Docker</div>
            <div className="meter" aria-hidden><i /></div>
            <div className="small" style={{ opacity: 0.8 }}>Подтверждено адаптивным тестом: 82 из 100</div>
            <div className="chips">
              <span className="chip">ФСП: призёр</span>
              <span className="chip">Тест пройден</span>
              <span className="chip">Открыт к офферу</span>
            </div>
            <div className="salary">
              от 180 000 до 240 000 ₽
              <span>зарплатная вилка указана в приглашении</span>
            </div>
          </div>
          </div>
          <div className="row">
            <Link to="/register?role=candidate" className="btn btn-white btn-lg">Я ищу работу</Link>
            <Link to="/register?role=employer" className="btn btn-light btn-lg">Я ищу специалистов</Link>
          </div>
          <div className="flow" aria-label="Путь кандидата">
            {[["1. Опрос", "отрасль, специализация, стек"], ["2. Грейд", "выбираете сами"], ["3. Тест", "адаптивный, 10–20 вопросов"], ["4. Категория", "видна работодателям"], ["5. Приглашение", "с вилкой зарплаты"]].map(([t, s]) => (
              <div className="item" key={t}><b>{t}</b>{s}</div>
            ))}
          </div>
        </div>
      </section>
      <div className="main stack-lg">
        <div className="grid grid-3">
          {FEATURES.map((f) => (
            <div className="card feature" key={f.title}>
              <div className="icon" aria-hidden>{f.icon}</div>
              <h3>{f.title}</h3>
              <p className="muted small" style={{ marginTop: 6 }}>{f.text}</p>
            </div>
          ))}
        </div>
        <div className="card card-accent">
          <div className="row-between">
            <div>
              <h3>Демо-доступ для проверки</h3>
              <p className="muted small" style={{ marginTop: 4 }}>
                Кандидат: <span className="mono">candidate@demo.ru</span> · Работодатель: <span className="mono">employer@demo.ru</span> · пароль <span className="mono">demo12345</span>.
                Можно и зарегистрироваться заново — ссылка подтверждения в демо-режиме показывается на экране.
              </p>
            </div>
            <Link to="/login" className="btn btn-primary">Войти</Link>
          </div>
        </div>
      </div>
    </>
  );
}
