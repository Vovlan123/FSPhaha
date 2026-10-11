import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { Bar, ErrorBox, Loading, StatusBadge, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { rub } from "../../format";
import type { CategoryCell, EmployerCompany, EmployerDashboard } from "../../types";
import { CompanyCta, markCompanyComplete } from "./common";

const INV_ORDER = ["sent", "viewed", "accepted", "declined", "expired", "withdrawn"];

function CategoryGrid({ cells }: { cells: CategoryCell[] }) {
  const d = useDict();
  const nav = useNavigate();
  const cell = (s: string, g: string) => cells.find((c) => c.specialization === s && c.grade === g);
  return (
    <div className="cat-grid-wrap">
      <div className="cat-grid" aria-label="Кандидаты по категориям">
        <div className="h" />
        {d.grades.map((g) => <div key={g.code} className="h">{g.label}</div>)}
        {d.specializations.map((s) => (
          <div key={s.code} style={{ display: "contents" }}>
            <div className="rh" title={s.label}>{s.short}</div>
            {d.grades.map((g) => {
              const c = cell(s.code, g.code);
              const n = c?.count ?? 0;
              return (
                <button
                  key={g.code}
                  type="button"
                  className={`cat-cell ${n === 0 ? "zero" : ""}`}
                  onClick={() => nav(`/employer/bank?specialization=${s.code}&grade=${g.code}`)}
                  title={`${s.short} · ${g.label}: открыть в банке кандидатов`}
                >
                  <div className="n">{n}</div>
                  <div className="sub">с ФСП: {c?.with_fsp ?? 0}</div>
                  {c?.median_salary ? <div className="med">медиана {rub(c.median_salary)}</div> : null}
                </button>
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EmployerDashboard() {
  const { data, error, loading } = useLoad(async () => {
    const company = await api<EmployerCompany>("/employer/company");
    if (!company.complete) return { company, dash: null };
    markCompanyComplete();
    return { company, dash: await api<EmployerDashboard>("/employer/dashboard") };
  });

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;
  if (!data.dash) return <CompanyCta />;

  const { dash } = data;
  const inv = dash.invitations;
  const active = (inv.sent ?? 0) + (inv.viewed ?? 0);
  const totalInv = Object.values(inv).reduce((a, b) => a + b, 0);
  const totalCandidates = dash.categories.reduce((a, c) => a + c.count, 0);

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1 className="row" style={{ gap: 10 }}>
            {dash.company.name}
            {dash.company.verified
              ? <span className="badge badge-green" style={{ fontSize: 13 }}>✓ Компания подтверждена</span>
              : <Link to="/employer/company" className="badge badge-amber" style={{ fontSize: 13 }}>Подтвердите компанию →</Link>}
          </h1>
          <p>Кабинет работодателя: опишите потребность — получите объяснённую подборку из подтверждённых кандидатов.</p>
        </div>
        <div className="row">
          <Link to="/employer/bank" className="btn btn-secondary">Банк кандидатов</Link>
          <Link to="/employer/needs/new" className="btn btn-primary">Описать потребность</Link>
        </div>
      </div>

      <div className="card hero-card stack">
        <h2>Здесь не ждут откликов — здесь приглашают</h2>
        <div className="flow">
          <div className="item"><b>1. Потребность</b>Вставьте текст — система разберёт стек, грейд и вилку</div>
          <div className="item"><b>2. Подборка</b>Кандидаты из категорий «специализация × грейд» с баллом 0–100</div>
          <div className="item"><b>3. Причины</b>Плюсы и минусы каждого: подтверждённый стек, ФСП, условия</div>
          <div className="item"><b>4. Приглашение</b>Конкретному кандидату и с обязательной зарплатной вилкой</div>
          <div className="item"><b>5. Контакты</b>Открываются, когда кандидат принимает приглашение</div>
        </div>
        <p className="small muted">
          Грейд каждого кандидата подтверждён адаптивным тестом, достижения — реестром ФСП. До ответа кандидат анонимен.
        </p>
      </div>

      <div className="grid grid-4">
        <div className="card stat">
          <span className="value">{totalCandidates}</span>
          <span className="label">кандидатов в банке</span>
        </div>
        <Link to="/employer/invitations" className="card card-link stat">
          <span className="value">{active}</span>
          <span className="label">активных приглашений · принято {inv.accepted ?? 0}</span>
        </Link>
        <div className="card stat">
          <span className="value">{dash.quota.left} <span className="small muted">из {dash.quota.limit}</span></span>
          <span className="label">приглашений осталось на неделе</span>
          <div style={{ marginTop: 8 }}><Bar value={dash.quota.left / Math.max(dash.quota.limit, 1)} /></div>
          {dash.quota.reason && <span className="tiny" style={{ color: "var(--amber)", marginTop: 6 }}>{dash.quota.reason}</span>}
        </div>
        <Link to="/employer/vacancies" className="card card-link stat">
          <span className="value">{dash.new_applications}</span>
          <span className="label">новых откликов на вакансии</span>
        </Link>
      </div>

      <div className="grid grid-2">
        <div className="card stack">
          <div className="card-head" style={{ marginBottom: 0 }}>
            <h3>Приглашения по статусам</h3>
            <Link to="/employer/invitations" className="small">Все приглашения →</Link>
          </div>
          {totalInv === 0 ? (
            <p className="muted small">Вы ещё никого не пригласили. Начните с потребности — подборка покажет, кого стоит позвать.</p>
          ) : (
            <div className="stack-sm">
              {INV_ORDER.filter((s) => inv[s]).map((s) => (
                <div key={s} className="row-between">
                  <StatusBadge kind="invitation" status={s} />
                  <span className="strong">{inv[s]}</span>
                </div>
              ))}
            </div>
          )}
        </div>
        <div className="card stack">
          <div className="card-head" style={{ marginBottom: 0 }}>
            <h3>Потребности</h3>
            <Link to="/employer/needs" className="small">Все потребности →</Link>
          </div>
          <p className="small muted">
            {dash.needs > 0
              ? `Описано потребностей: ${dash.needs}. Подборка хранится и уточняется фильтрами, шорт-лист сохраняется при пересчёте.`
              : "Потребностей пока нет. Опишите, кого ищете, своими словами — поля заполнятся автоматически."}
          </p>
          <div>
            <Link to="/employer/needs/new" className="btn btn-primary btn-sm">Описать потребность</Link>
          </div>
        </div>
      </div>

      <div className="card stack">
        <div className="card-head" style={{ marginBottom: 0 }}>
          <div>
            <h3>Категории кандидатов</h3>
            <p className="small muted">Специализация × грейд по результату теста. Нажмите на ячейку, чтобы открыть кандидатов в банке.</p>
          </div>
        </div>
        <CategoryGrid cells={dash.categories} />
      </div>
    </div>
  );
}
