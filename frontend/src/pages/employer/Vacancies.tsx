import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import SalaryFields, { parseRub, salaryError } from "../../components/SalaryFields";
import { ChipSelect, Empty, ErrorBox, Field, Loading, Modal, Salary, ScoreRing, StatusBadge, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { ago, dateShort, plural } from "../../format";
import type { Application, Vacancy } from "../../types";
import { BlueprintModal, CompanyGate } from "./common";

type Form = {
  title: string;
  description: string;
  specialization: string;
  grade: string;
  stack: string[];
  work_format: string[];
  city: string;
  salary_from: string;
  salary_to: string;
  status: "published" | "closed";
};

function toForm(v?: Vacancy): Form {
  if (!v) return { title: "", description: "", specialization: "", grade: "", stack: [], work_format: [], city: "", salary_from: "", salary_to: "", status: "published" };
  return {
    title: v.title, description: v.description, specialization: v.specialization, grade: v.grade, stack: v.stack,
    work_format: v.work_format, city: v.city, salary_from: String(v.salary_from), salary_to: String(v.salary_to),
    status: v.status === "closed" ? "closed" : "published",
  };
}

function vacancyBody(f: Form) {
  return {
    title: f.title.trim(), description: f.description.trim(), specialization: f.specialization, grade: f.grade, stack: f.stack,
    work_format: f.work_format, city: f.city.trim(), salary_from: parseRub(f.salary_from), salary_to: parseRub(f.salary_to), status: f.status,
  };
}

function VacancyFormModal({ vacancy, onClose, onSaved }: { vacancy?: Vacancy; onClose: () => void; onSaved: () => void }) {
  const d = useDict();
  const [form, setForm] = useState<Form>(() => toForm(vacancy));
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const patch = (p: Partial<Form>) => setForm((f) => ({ ...f, ...p }));

  const spec = d.specializations.find((s) => s.code === form.specialization);
  const base = spec?.skills ?? [];
  const skillOptions = [...base, ...form.stack.filter((s) => !base.includes(s))].map((s) => ({ code: s, label: d.skill(s) }));
  const grade = d.grades.find((g) => g.code === form.grade);

  const errs = {
    title: form.title.trim().length < 3 ? "Название не короче 3 символов" : null,
    specialization: form.specialization ? null : "Выберите специализацию",
    grade: form.grade ? null : "Выберите грейд",
    salary: salaryError(form.salary_from, form.salary_to),
  };
  const valid = !errs.title && !errs.specialization && !errs.grade && !errs.salary;

  async function save() {
    setTried(true);
    setError(null);
    if (!valid) return;
    setBusy(true);
    try {
      if (vacancy) await api(`/employer/vacancies/${vacancy.id}`, { method: "PUT", body: vacancyBody(form) });
      else await api("/employer/vacancies", { body: vacancyBody(form) });
      toast(vacancy ? "Вакансия сохранена" : "Вакансия опубликована");
      onSaved();
      onClose();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      title={vacancy ? "Редактировать вакансию" : "Новая вакансия"}
      onClose={onClose}
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={busy}>Отмена</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Сохраняем…" : vacancy ? "Сохранить" : "Опубликовать"}</button>
        </>
      }
    >
      <div className="stack">
        <Field label="Название *" error={tried ? errs.title : null}>
          <input className={`input ${tried && errs.title ? "invalid" : ""}`} value={form.title} maxLength={200} onChange={(e) => patch({ title: e.target.value })} />
        </Field>
        <Field label="Описание">
          <textarea className="textarea" value={form.description} maxLength={8000} onChange={(e) => patch({ description: e.target.value })} />
        </Field>
        <div className="grid grid-2">
          <Field label="Специализация *" error={tried ? errs.specialization : null}>
            <select className="select" value={form.specialization} onChange={(e) => patch({ specialization: e.target.value })}>
              <option value="">Выберите</option>
              {d.specializations.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Грейд *" error={tried ? errs.grade : null} hint={grade ? `${grade.years}. ${grade.description}` : undefined}>
            <select className="select" value={form.grade} onChange={(e) => patch({ grade: e.target.value })}>
              <option value="">Выберите</option>
              {d.grades.map((g) => <option key={g.code} value={g.code}>{g.label} · {g.years}</option>)}
            </select>
          </Field>
        </div>
        <Field label="Стек" hint={spec ? "По стеку и грейду система сформирует задания для кандидатов" : "Выберите специализацию, чтобы увидеть справочник навыков"}>
          <ChipSelect options={skillOptions} value={form.stack} onChange={(v) => patch({ stack: v })} />
        </Field>
        <div className="grid grid-2">
          <Field label="Формат работы">
            <ChipSelect options={d.work_formats} value={form.work_format} onChange={(v) => patch({ work_format: v })} />
          </Field>
          <Field label="Город">
            <input className="input" value={form.city} maxLength={100} onChange={(e) => patch({ city: e.target.value })} />
          </Field>
        </div>
        <SalaryFields from={form.salary_from} to={form.salary_to} onFrom={(v) => patch({ salary_from: v })} onTo={(v) => patch({ salary_to: v })} showError={tried} />
        <Field label="Статус">
          <select className="select" value={form.status} onChange={(e) => patch({ status: e.target.value as Form["status"] })}>
            <option value="published">Опубликована — видна кандидатам</option>
            <option value="closed">Закрыта — снята с публикации</option>
          </select>
        </Field>
        <ErrorBox error={error} />
      </div>
    </Modal>
  );
}

function ApplicationsPanel({ vacancy, onLoaded }: { vacancy: Vacancy; onLoaded: () => void }) {
  // Открытие списка помечает новые отклики просмотренными на сервере
  const { data, error, loading, setData } = useLoad(async () => {
    const list = await api<Application[]>(`/employer/vacancies/${vacancy.id}/applications`);
    onLoaded();
    return list;
  }, [vacancy.id]);
  const [busy, setBusy] = useState<number | null>(null);

  async function setStatus(a: Application, status: "invited" | "rejected") {
    setBusy(a.id);
    try {
      const updated = await api<Application>(`/employer/applications/${a.id}/status`, { body: { status } });
      setData((prev) => prev && prev.map((x) => (x.id === a.id ? updated : x)));
      toast(status === "invited" ? "Кандидат приглашён на интервью" : "Отклик отклонён");
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  if (data.length === 0) return <Empty icon="✉" title="Откликов нет">Кандидаты увидят вакансию в своём кабинете с процентом соответствия.</Empty>;

  return (
    <div className="stack">
      {data.map((a) => {
        const c = a.candidate;
        const tg = c?.contacts.telegram?.replace(/^@/, "");
        return (
          <div key={a.id} className="card card-tight cand" style={{ boxShadow: "none" }}>
            <div>{a.match_score !== null ? <ScoreRing value={a.match_score} /> : <span className="tiny muted">—</span>}</div>
            <div className="stack-sm" style={{ minWidth: 0 }}>
              <div className="row" style={{ gap: 8 }}>
                {c ? <Link to={`/employer/candidates/${c.id}`} className="cand-name">{c.display_name}</Link> : <span className="cand-name">Кандидат</span>}
                {c?.category && <span className="category">{c.category}</span>}
                <StatusBadge kind="application" status={a.status} label={a.status_label} />
                <span className="tiny muted">{ago(a.created_at)}</span>
              </div>
              {c && (
                <div className="contacts-box row" style={{ gap: "4px 16px" }}>
                  <span className="strong">Кандидат откликнулся сам — контакты открыты:</span>
                  {c.contacts.email && <a href={`mailto:${c.contacts.email}`}>{c.contacts.email}</a>}
                  {c.contacts.phone && <a href={`tel:${c.contacts.phone}`}>{c.contacts.phone}</a>}
                  {tg && <a href={`https://t.me/${tg}`} target="_blank" rel="noreferrer">@{tg}</a>}
                </div>
              )}
              {a.cover_letter ? <div className="quote">{a.cover_letter}</div> : <span className="small muted">Без сопроводительного письма</span>}
            </div>
            <div className="cand-actions">
              <button className="btn btn-success btn-sm" onClick={() => setStatus(a, "invited")} disabled={busy === a.id || a.status === "invited"}>
                {a.status === "invited" ? "Приглашён на интервью" : "Пригласить на интервью"}
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => setStatus(a, "rejected")} disabled={busy === a.id || a.status === "rejected"}>
                {a.status === "rejected" ? "Отказано" : "Отказать"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function VacancyCard({ v, onEdit, onToggleStatus, toggling, onBlueprint, onViewed }: {
  v: Vacancy; onEdit: () => void; onToggleStatus: () => void; toggling: boolean; onBlueprint: () => void; onViewed: () => void;
}) {
  const d = useDict();
  const [open, setOpen] = useState(false);
  const apps = v.applications ?? 0;
  return (
    <div className="card stack-sm">
      <div className="row-between" style={{ alignItems: "flex-start" }}>
        <div className="stack-sm" style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <h3>{v.title}</h3>
            {v.category && <span className="category">{v.category}</span>}
            <StatusBadge kind="vacancy" status={v.status} />
          </div>
          <div className="chips">{v.stack.map((s) => <span key={s} className="skill">{d.skill(s)}</span>)}</div>
        </div>
        <Salary from={v.salary_from} to={v.salary_to} />
      </div>
      <div className="cand-meta">
        <span>{v.work_format.length ? v.work_format.map((f) => d.label(d.work_formats, f)).join(", ") : "любой формат"}</span>
        {v.city && <span>{v.city}</span>}
        <span>создана {dateShort(v.created_at)}</span>
        <span>
          {apps} {plural(apps, "отклик", "отклика", "откликов")}
          {v.new_applications ? <span className="badge badge-amber" style={{ marginLeft: 6 }}>{v.new_applications} {plural(v.new_applications, "новый", "новых", "новых")}</span> : null}
        </span>
      </div>
      <div className="row" style={{ marginTop: 6 }}>
        <button className={`btn btn-sm ${open ? "btn-primary" : "btn-secondary"}`} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? "Скрыть отклики" : `Отклики (${apps})`}
        </button>
        <button className="btn btn-secondary btn-sm" onClick={onEdit}>Изменить</button>
        <button className="btn btn-ghost btn-sm" onClick={onBlueprint}>Задания для кандидатов</button>
        <button className="btn btn-ghost btn-sm" onClick={onToggleStatus} disabled={toggling}>
          {v.status === "published" ? "Снять с публикации" : "Опубликовать снова"}
        </button>
      </div>
      {open && (
        <div style={{ marginTop: 10 }}>
          <ApplicationsPanel vacancy={v} onLoaded={onViewed} />
        </div>
      )}
    </div>
  );
}

function VacanciesView() {
  const { data, error, loading, reload, setData } = useLoad(() => api<Vacancy[]>("/employer/vacancies"));
  const [editing, setEditing] = useState<Vacancy | "new" | null>(null);
  const [blueprint, setBlueprint] = useState<Vacancy | null>(null);
  const [toggling, setToggling] = useState<number | null>(null);

  async function toggleStatus(v: Vacancy) {
    setToggling(v.id);
    try {
      const status = v.status === "published" ? "closed" : "published";
      const updated = await api<Vacancy>(`/employer/vacancies/${v.id}`, { method: "PUT", body: { ...vacancyBody(toForm(v)), status } });
      setData((prev) => prev && prev.map((x) => (x.id === v.id ? { ...x, ...updated } : x)));
      toast(status === "closed" ? "Вакансия снята с публикации" : "Вакансия опубликована");
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setToggling(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Вакансии</h1>
          <p>Вакансия с обязательной вилкой видна кандидатам. Откликнувшийся кандидат сразу открывает вам свои контакты.</p>
        </div>
        <button className="btn btn-primary" onClick={() => setEditing("new")}>Новая вакансия</button>
      </div>

      {data.length === 0 ? (
        <div className="card">
          <Empty icon="▤" title="Вакансий пока нет">
            <p>Опубликуйте вакансию — кандидаты увидят её с процентом соответствия своему профилю.</p>
            <div style={{ marginTop: 14 }}>
              <button className="btn btn-primary" onClick={() => setEditing("new")}>Новая вакансия</button>
            </div>
          </Empty>
        </div>
      ) : (
        <div className="stack">
          {data.map((v) => (
            <VacancyCard
              key={v.id}
              v={v}
              onEdit={() => setEditing(v)}
              onToggleStatus={() => toggleStatus(v)}
              toggling={toggling === v.id}
              onBlueprint={() => setBlueprint(v)}
              onViewed={() => setData((prev) => prev && prev.map((x) => (x.id === v.id ? { ...x, new_applications: 0 } : x)))}
            />
          ))}
        </div>
      )}

      {editing && (
        <VacancyFormModal vacancy={editing === "new" ? undefined : editing} onClose={() => setEditing(null)} onSaved={() => void reload()} />
      )}
      {blueprint && (
        <BlueprintModal path={`/vacancies/${blueprint.id}/blueprint`} title={`Какие задания получит кандидат · ${blueprint.title}`} onClose={() => setBlueprint(null)} />
      )}
    </div>
  );
}

export default function EmployerVacancies() {
  return (
    <CompanyGate>
      <VacanciesView />
    </CompanyGate>
  );
}
