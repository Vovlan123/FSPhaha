import { useState } from "react";
import { api } from "../api";
import BlueprintView from "../components/BlueprintView";
import { ChipSelect, ErrorBox, Field, Loading, Tabs, useLoad } from "../components/ui";
import { useDict } from "../dict";
import type { Blueprint } from "../types";

type BankRow = {
  id: string; pool: string; title: string; fmt: string; a: number; b: number; variants: number; topics: string[];
  exposures: number; p_correct: number | null; mean_residual: number | null; status: string;
};

export default function HowItWorks() {
  const [tab, setTab] = useState<"test" | "match" | "fsp" | "bank">("test");
  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Как это работает</h1>
          <p>Механика тестирования, подбора и интеграции с ФСП — с живыми данными из системы.</p>
        </div>
      </div>
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "test", label: "Тестирование" },
          { key: "match", label: "Подбор и контакт" },
          { key: "fsp", label: "ФСП ID" },
          { key: "bank", label: "Банк заданий" },
        ]}
      />
      {tab === "test" && <TestMechanics />}
      {tab === "match" && <MatchMechanics />}
      {tab === "fsp" && <FspMechanics />}
      {tab === "bank" && <BankHealth />}
    </div>
  );
}

function TestMechanics() {
  const d = useDict();
  const [spec, setSpec] = useState("backend");
  const [grade, setGrade] = useState("middle");
  const [stack, setStack] = useState<string[]>(["python", "sql", "postgresql"]);
  const skills = d.specializations.find((s) => s.code === spec)?.skills ?? [];
  const bp = useLoad(() => api<Blueprint>(`/system/blueprint?specialization=${spec}&grade=${grade}&stack=${stack.join(",")}`), [spec, grade, stack.join(",")]);
  return (
    <div className="stack">
      <div className="grid grid-3">
        <div className="card">
          <h3>Параметрические шаблоны</h3>
          <p className="small muted" style={{ marginTop: 6 }}>
            Задание — не текст, а генератор: числа, имена, порядок строк кода и вариантов меняются. Слитый ответ на
            один экземпляр не подходит к другому, а сложность у всех экземпляров одного шаблона одинакова.
          </p>
        </div>
        <div className="card">
          <h3>IRT и адаптивный тест</h3>
          <p className="small muted" style={{ marginTop: 6 }}>
            У каждого шаблона есть параметры модели 2PL: сложность b и различающая способность a. Следующий вопрос
            подбирается под текущую оценку уровня θ. Тест останавливается, когда решение по грейду статистически
            уверенно (10–20 вопросов).
          </p>
        </div>
        <div className="card">
          <h3>Защита от утечек</h3>
          <p className="small muted" style={{ marginTop: 6 }}>
            Случайный выбор из лучших вопросов, контроль частоты показов, повтор на тот же грейд — через 30 дней, смена
            грейда — раз в 90 дней. Детектор утечек отправляет шаблон в карантин, если по нему отвечают лучше, чем
            предсказывает модель.
          </p>
        </div>
      </div>
      <div className="card stack">
        <h3>Попробуйте: как система соберёт тест под вакансию</h3>
        <div className="grid grid-3">
          <Field label="Специализация">
            <select className="select" value={spec} onChange={(e) => { setSpec(e.target.value); setStack([]); }}>
              {d.specializations.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Грейд">
            <select className="select" value={grade} onChange={(e) => setGrade(e.target.value)}>
              {d.grades.map((g) => <option key={g.code} value={g.code}>{g.label}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Стек вакансии">
          <ChipSelect options={skills.map((s) => ({ code: s, label: d.skill(s) }))} value={stack} onChange={setStack} />
        </Field>
        <ErrorBox error={bp.error} />
        {bp.loading && !bp.data ? <Loading /> : bp.data && <BlueprintView bp={bp.data} />}
      </div>
    </div>
  );
}

function MatchMechanics() {
  return (
    <div className="stack">
      <div className="card stack-sm">
        <h3>Обратная механика</h3>
        <ol className="small" style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
          <li>Работодатель описывает потребность текстом — NLP-разбор заполняет специализацию, грейд, стек, формат и вилку.</li>
          <li>Система показывает рекомендованные категории: основную, соседние по грейду и смежные специализации.</li>
          <li>Внутри — ранжированный список с баллом соответствия и причинами «почему в подборке».</li>
          <li>Фильтры уточняют сохранённую подборку, шорт-лист переживает пересчёт.</li>
          <li>Работодатель отправляет приглашение с обязательной вилкой «от–до». Квота — 20 в неделю, чтобы выбирать, а не спамить.</li>
          <li>Кандидат видит условия до общения, принимает или отклоняет с причиной. Контакты открываются только после принятия.</li>
        </ol>
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h3>Сила подтверждённого профиля</h3>
          <p className="mono small" style={{ margin: "10px 0" }}>P = 0,60·T + 0,25·F + 0,15·A</p>
          <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
            <li><b>T</b> — положение θ внутри полосы грейда (результат теста)</li>
            <li><b>F</b> — балл ФСП: уровень × результат × затухание по давности</li>
            <li><b>A</b> — активность: оценки регулярных заданий за последние месяцы</li>
          </ul>
          <p className="small" style={{ marginTop: 8 }}>По P ранжируются кандидаты внутри категории.</p>
        </div>
        <div className="card">
          <h3>Соответствие потребности</h3>
          <p className="mono small" style={{ margin: "10px 0" }}>Score = 40·S + 20·P + 25·G + 15·C</p>
          <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
            <li><b>S</b> — стек: заявленный и подтверждённый тестом навык весит 1,0, только заявленный — 0,8, опровергнутый тестом — 0,3; плюс TF-IDF-близость описаний</li>
            <li><b>G</b> — категория: грейд совпадает 1,0, на ступень выше 0,4, ниже 0,35</li>
            <li><b>C</b> — условия: зарплата, формат, город</li>
          </ul>
          <p className="small" style={{ marginTop: 8 }}>Каждый фактор превращается в понятную причину в выдаче.</p>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="card">
          <h3>Защита от недобросовестных работодателей</h3>
          <ul className="small muted" style={{ margin: "10px 0 0", paddingLeft: 18 }}>
            <li>Подтверждение компании: ИНН с проверкой контрольной суммы ФНС и email на домене сайта</li>
            <li>Неподтверждённой компании — 5 приглашений в неделю вместо 20</li>
            <li>В каждом приглашении — блок «Надёжность работодателя»: подтверждение, доля принятых приглашений, жалобы, массовая рассылка, вилка ниже рынка</li>
            <li>Жалоба закрывает приглашение без раскрытия контактов; при 3 жалобах приглашения компании приостанавливаются</li>
          </ul>
        </div>
        <div className="card">
          <h3>Интеграция с ATS</h3>
          <ul className="small muted" style={{ margin: "10px 0 0", paddingLeft: 18 }}>
            <li>Вебхуки: приглашение принято или отклонено, новый отклик, решение задания</li>
            <li>Подпись <span className="mono">X-FSP-Signature: sha256=HMAC(секрет, тело)</span>, ключ идемпотентности, до 3 попыток</li>
            <li>Журнал доставок и тестовое событие в профиле компании</li>
            <li>Экспорт кандидата в JSON после раскрытия контактов</li>
          </ul>
        </div>
      </div>
    </div>
  );
}

function FspMechanics() {
  return (
    <div className="grid grid-2">
      <div className="card stack-sm">
        <h3>Привязка ФСП ID</h3>
        <p className="small muted">
          OAuth 2.0 / OpenID Connect, пути совместимы с Keycloak (<span className="mono">/realms/fsp/protocol/openid-connect/*</span>).
          Кандидат входит в ФСП ID, платформа получает его идентификатор участника и достижения. Для перехода на боевой
          Keycloak ФСП достаточно сменить адрес и ключи клиента.
        </p>
        <p className="small muted">Обновление достижений — по сервисному аккаунту (client credentials), отвязка удаляет снимок.</p>
      </div>
      <div className="card stack-sm">
        <h3>Что берём из реестра</h3>
        <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
          <li>Соревнование и дисциплина (алгоритмическое, продуктовое, ИБ, робототехника, БАС)</li>
          <li>Уровень: международный, всероссийский, межрегиональный, региональный, локальный</li>
          <li>Результат и место, команда и роль (капитан или участник), дата</li>
        </ul>
        <p className="small">Нет истории ФСП — без штрафа и ошибок: профиль показывается с плашкой «Нет данных ФСП».</p>
      </div>
    </div>
  );
}

function BankHealth() {
  const [pool, setPool] = useState("all");
  const r = useLoad(() => api<{ total: number; quarantined: number; templates: BankRow[] }>("/system/bank-health"), []);
  if (r.loading && !r.data) return <Loading />;
  if (r.error) return <ErrorBox error={r.error} />;
  const rows = (r.data?.templates ?? []).filter((t) => pool === "all" || t.pool === pool);
  const pools = Array.from(new Set((r.data?.templates ?? []).map((t) => t.pool)));
  return (
    <div className="card stack">
      <div className="row-between">
        <div>
          <h3>Шаблонов в банке: {r.data?.total} · в карантине: {r.data?.quarantined}</h3>
          <p className="small muted">Средний остаток — насколько чаще отвечают верно, чем предсказывает модель. Устойчиво больше 0,2 — признак утечки.</p>
        </div>
        <select className="select" style={{ width: 200 }} value={pool} onChange={(e) => setPool(e.target.value)} aria-label="Пул">
          <option value="all">Все пулы</option>
          {pools.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
      </div>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Шаблон</th><th>Пул</th><th>a</th><th>b</th><th>Показов</th><th>Доля верных</th><th>Ср. остаток</th><th>Статус</th></tr></thead>
          <tbody>
            {rows.map((t) => (
              <tr key={t.id}>
                <td><div className="strong small">{t.title}</div><div className="tiny muted mono">{t.id}</div></td>
                <td className="small">{t.pool}</td>
                <td className="mono small">{t.a.toFixed(2)}</td>
                <td className="mono small">{t.b.toFixed(2)}</td>
                <td className="small">{t.exposures}</td>
                <td className="small">{t.p_correct === null ? "—" : `${Math.round(t.p_correct * 100)}%`}</td>
                <td className="mono small">{t.mean_residual === null ? "—" : t.mean_residual.toFixed(3)}</td>
                <td><span className={`badge ${t.status === "active" ? "badge-green" : "badge-red"}`}>{t.status === "active" ? "активен" : "карантин"}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
