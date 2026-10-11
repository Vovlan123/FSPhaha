import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import InviteModal from "../../components/InviteModal";
import { Bar, ChipSelect, Empty, ErrorBox, Field, Loading, SkillTags, StatusBadge, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { plural, rub, years } from "../../format";
import type { CandidateSummary } from "../../types";
import { CompanyGate, isActiveInvitation } from "./common";

const LIMIT = 30;
const SORTS = [
  { code: "strength", label: "Сила профиля" },
  { code: "theta", label: "Уровень по тесту (θ)" },
  { code: "fsp", label: "Достижения ФСП" },
  { code: "salary", label: "Ожидания: сначала ниже" },
];
const MAX_SKILLS = 7;

function BankRow({ c, onInvite }: { c: CandidateSummary; onInvite: () => void }) {
  const d = useDict();
  // Сначала подтверждённые тестом навыки, затем заявленные
  const skills = Array.from(new Set([...c.verified_skills, ...c.stack]));  // подтверждённые тестом — первыми
  const s = c.strength;
  return (
    <tr>
      <td>
        <Link to={`/employer/candidates/${c.id}`} className="strong">{c.display_name}</Link>
        <div className="tiny muted">
          {c.anon_code} · {c.city || "город не указан"} · {years(c.experience_years)}
        </div>
      </td>
      <td>
        <span className="category">{c.category}</span>
        <div className="tiny muted" style={{ marginTop: 4 }}>{d.label(d.job_statuses, c.job_status)}</div>
      </td>
      <td style={{ minWidth: 130 }}>
        <div className="row-between small"><span className="strong">{Math.round(s.P * 100)}</span><span className="tiny muted">из 100</span></div>
        <Bar value={s.P} />
        <div className="tiny muted" style={{ marginTop: 3 }}>
          тест {Math.round(s.T * 100)} · ФСП {Math.round(s.F * 100)} · акт. {Math.round(s.A * 100)}
        </div>
      </td>
      <td style={{ minWidth: 220 }}>
        <SkillTags skills={skills.slice(0, MAX_SKILLS)} verified={c.verified_skills} refuted={c.refuted_skills} />
        {skills.length > MAX_SKILLS && <div className="tiny muted" style={{ marginTop: 3 }}>и ещё {skills.length - MAX_SKILLS}</div>}
      </td>
      <td>
        {c.has_fsp ? <span className="badge badge-solid" title={c.fsp_top ?? undefined}>ФСП</span> : <span className="muted small">—</span>}
      </td>
      <td className="nowrap small">{c.salary_expect_min ? `от ${rub(c.salary_expect_min)}` : <span className="muted">скрыты</span>}</td>
      <td>{c.invitation ? <StatusBadge kind="invitation" status={c.invitation.status} /> : <span className="muted small">—</span>}</td>
      <td>
        <div className="row" style={{ gap: 6, flexWrap: "nowrap" }}>
          <Link to={`/employer/candidates/${c.id}`} className="btn btn-secondary btn-sm">Профиль</Link>
          {!isActiveInvitation(c.invitation?.status) && c.invitation?.status !== "accepted" && (
            <button className="btn btn-success btn-sm" onClick={onInvite}>Пригласить</button>
          )}
        </div>
      </td>
    </tr>
  );
}

function BankView() {
  const d = useDict();
  const [params, setParams] = useSearchParams();
  const [inviting, setInviting] = useState<CandidateSummary | null>(null);

  const specialization = params.get("specialization") ?? "";
  const grade = params.get("grade") ?? "";
  const stack = (params.get("stack") ?? "").split(",").filter(Boolean);
  const verifiedOnly = params.get("verified_only") === "1";
  const hasFsp = params.get("has_fsp") === "1";
  const q = params.get("q") ?? "";
  const sort = params.get("sort") ?? "strength";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const [qInput, setQInput] = useState(q);
  useEffect(() => setQInput(q), [q]);

  function update(patch: Record<string, string | null>, keepPage = false) {
    // Функциональное обновление: отложенный поиск не затрёт фильтр, изменённый за время задержки
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [k, v] of Object.entries(patch)) {
          if (v) next.set(k, v);
          else next.delete(k);
        }
        if (!keepPage) next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  // Поиск по тексту применяется с небольшой задержкой, чтобы не дёргать API на каждую букву
  useEffect(() => {
    if (qInput.trim() === q) return;
    const t = window.setTimeout(() => update({ q: qInput.trim() || null }), 400);
    return () => window.clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [qInput]);

  const apiQs = useMemo(() => {
    const p = new URLSearchParams();
    if (specialization) p.set("specialization", specialization);
    if (grade) p.set("grade", grade);
    if (stack.length) p.set("stack", stack.join(","));
    if (verifiedOnly) p.set("verified_only", "true");
    if (hasFsp) p.set("has_fsp", "true");
    if (q) p.set("q", q);
    p.set("sort", sort);
    p.set("limit", String(LIMIT));
    p.set("offset", String((page - 1) * LIMIT));
    return p.toString();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [params]);

  const { data, error, loading, setData } = useLoad(
    () => api<{ total: number; items: CandidateSummary[] }>(`/employer/candidates?${apiQs}`),
    [apiQs],
  );

  const spec = d.specializations.find((s) => s.code === specialization);
  const hasFilters = !!(specialization || grade || stack.length || verifiedOnly || hasFsp || q);
  const total = data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / LIMIT));
  const reset = () => setParams(sort !== "strength" ? new URLSearchParams({ sort }) : new URLSearchParams(), { replace: true });

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Банк кандидатов</h1>
          <p>Все категоризированные кандидаты, согласившиеся на публикацию. Грейд подтверждён тестом, контакты скрыты до ответа на приглашение.</p>
        </div>
        <Link to="/employer/needs/new" className="btn btn-secondary">Подбор по потребности</Link>
      </div>

      <div className="card stack">
        <div className="grid grid-4">
          <Field label="Специализация">
            <select className="select" value={specialization} onChange={(e) => update({ specialization: e.target.value || null, stack: null })}>
              <option value="">Все специализации</option>
              {d.specializations.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Грейд">
            <select className="select" value={grade} onChange={(e) => update({ grade: e.target.value || null })}>
              <option value="">Все грейды</option>
              {d.grades.map((g) => <option key={g.code} value={g.code}>{g.label}</option>)}
            </select>
          </Field>
          <Field label="Поиск">
            <input className="input" type="search" value={qInput} onChange={(e) => setQInput(e.target.value)} placeholder="Навык или код К-1000" />
          </Field>
          <Field label="Сортировка">
            <select className="select" value={sort} onChange={(e) => update({ sort: e.target.value === "strength" ? null : e.target.value })}>
              {SORTS.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
          </Field>
        </div>
        {spec ? (
          <Field label={`Стек · ${spec.short}`} hint="Кандидат владеет всеми выбранными навыками">
            <ChipSelect
              options={spec.skills.map((s) => ({ code: s, label: d.skill(s) }))}
              value={stack}
              onChange={(v) => update({ stack: v.join(",") || null })}
            />
          </Field>
        ) : (
          <p className="small muted">Выберите специализацию, чтобы фильтровать по стеку.</p>
        )}
        <div className="row-between">
          <div className="row" style={{ gap: 20 }}>
            <label className="check">
              <input type="checkbox" checked={verifiedOnly} onChange={(e) => update({ verified_only: e.target.checked ? "1" : null })} />
              <span>Только подтверждённые тестом{!stack.length && <span className="muted small"> (для выбранного стека)</span>}</span>
            </label>
            <label className="check">
              <input type="checkbox" checked={hasFsp} onChange={(e) => update({ has_fsp: e.target.checked ? "1" : null })} />
              <span>С достижениями ФСП</span>
            </label>
          </div>
          {hasFilters && <button className="btn btn-ghost btn-sm" onClick={reset}>Сбросить фильтры</button>}
        </div>
      </div>

      <ErrorBox error={error} />
      {!data && loading ? (
        <Loading />
      ) : data && data.items.length === 0 ? (
        <div className="card">
          <Empty icon="⌕" title="Кандидатов по фильтрам нет — ослабьте фильтры">
            <p>Попробуйте убрать часть навыков, выбрать соседний грейд или отключить «только подтверждённые тестом».</p>
            {hasFilters && (
              <div style={{ marginTop: 14 }}>
                <button className="btn btn-secondary" onClick={reset}>Сбросить фильтры</button>
              </div>
            )}
          </Empty>
        </div>
      ) : data ? (
        <div className={`card stack ${loading ? "emp-busy" : ""}`} style={{ padding: 0 }}>
          <div className="row-between" style={{ padding: "14px 16px 0" }}>
            <span className="small">
              Найдено <b>{total}</b> {plural(total, "кандидат", "кандидата", "кандидатов")}
              {pages > 1 && <span className="muted"> · {(page - 1) * LIMIT + 1}–{Math.min(page * LIMIT, total)}</span>}
            </span>
            <span className="tiny muted"><span className="skill verified">✓ навык</span> — подтверждён тестом</span>
          </div>
          <div className="table-wrap">
            <table className="table" style={{ minWidth: 980 }}>
              <thead>
                <tr>
                  <th>Кандидат</th><th>Категория</th><th>Сила профиля</th><th>Навыки</th><th>ФСП</th><th>Ожидания</th><th>Приглашение</th><th />
                </tr>
              </thead>
              <tbody>
                {data.items.map((c) => <BankRow key={c.id} c={c} onInvite={() => setInviting(c)} />)}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <div className="row" style={{ justifyContent: "center", padding: "0 16px 16px" }}>
              <button className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => update({ page: page > 2 ? String(page - 1) : null }, true)}>← Назад</button>
              <span className="small muted">Страница {page} из {pages}</span>
              <button className="btn btn-secondary btn-sm" disabled={page >= pages} onClick={() => update({ page: String(page + 1) }, true)}>Вперёд →</button>
            </div>
          )}
        </div>
      ) : null}

      {inviting && (
        <InviteModal
          candidate={{ id: inviting.id, display_name: inviting.display_name, category: inviting.category, salary_expect_min: inviting.salary_expect_min }}
          onClose={() => setInviting(null)}
          onSent={(inv) =>
            setData((prev) => prev && { ...prev, items: prev.items.map((x) => (x.id === inviting.id ? { ...x, invitation: { id: inv.id, status: inv.status } } : x)) })
          }
        />
      )}
    </div>
  );
}

export default function BankPage() {
  return (
    <CompanyGate>
      <BankView />
    </CompanyGate>
  );
}
