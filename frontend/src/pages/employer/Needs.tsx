import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { Empty, ErrorBox, Loading, Salary, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { ago } from "../../format";
import type { Need } from "../../types";
import { CompanyGate } from "./common";

function NeedsList() {
  const d = useDict();
  const { data, error, loading, setData } = useLoad(() => api<Need[]>("/employer/needs"));
  const [deleting, setDeleting] = useState<number | null>(null);

  async function remove(n: Need) {
    if (!window.confirm(`Удалить потребность «${n.title}» вместе с подборкой и шорт-листом?`)) return;
    setDeleting(n.id);
    try {
      await api(`/employer/needs/${n.id}`, { method: "DELETE" });
      setData((list) => (list ?? []).filter((x) => x.id !== n.id));
      toast("Потребность удалена");
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setDeleting(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  const needs = data ?? [];

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Подбор по потребностям</h1>
          <p>Опишите, кого ищете, — система соберёт ранжированную подборку и объяснит, почему каждый кандидат в ней.</p>
        </div>
        <Link to="/employer/needs/new" className="btn btn-primary">Описать потребность</Link>
      </div>

      {needs.length === 0 ? (
        <div className="card">
          <Empty icon="◎" title="Потребностей пока нет">
            <p>Вставьте текст вакансии или опишите задачу своими словами — специализация, грейд, стек и вилка заполнятся автоматически.</p>
            <div style={{ marginTop: 14 }}>
              <Link to="/employer/needs/new" className="btn btn-primary">Описать потребность</Link>
            </div>
          </Empty>
        </div>
      ) : (
        <div className="stack">
          {needs.map((n) => (
            <div key={n.id} className="card stack-sm">
              <div className="row-between" style={{ alignItems: "flex-start" }}>
                <div className="stack-sm" style={{ minWidth: 0 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <Link to={`/employer/needs/${n.id}`}><h3>{n.title}</h3></Link>
                    {n.category && <span className="category">{n.category}</span>}
                  </div>
                  <div className="chips">
                    {n.stack_must.map((s) => <span key={s} className="skill verified" title="Обязательный навык">{d.skill(s)}</span>)}
                    {n.stack_nice.map((s) => <span key={s} className="skill" title="Желательный навык">{d.skill(s)}</span>)}
                  </div>
                </div>
                <Salary from={n.salary_from} to={n.salary_to} />
              </div>
              <div className="cand-meta">
                <span>{n.work_format.length ? n.work_format.map((f) => d.label(d.work_formats, f)).join(", ") : "любой формат"}</span>
                {n.city && <span>{n.city}</span>}
                <span>в подборке: <b style={{ color: "var(--ink)" }}>{n.selection_size ?? 0}</b></span>
                <span>в шорт-листе: <b style={{ color: "var(--ink)" }}>{n.pinned ?? 0}</b></span>
                <span>обновлена {ago(n.updated_at ?? n.selection_at)}</span>
              </div>
              <div className="row" style={{ marginTop: 6 }}>
                <Link to={`/employer/needs/${n.id}`} className="btn btn-primary btn-sm">Подборка</Link>
                <Link to={`/employer/needs/${n.id}/edit`} className="btn btn-secondary btn-sm">Изменить</Link>
                <button className="btn btn-ghost btn-sm" onClick={() => remove(n)} disabled={deleting === n.id}>
                  {deleting === n.id ? "Удаляем…" : "Удалить"}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NeedsPage() {
  return (
    <CompanyGate>
      <NeedsList />
    </CompanyGate>
  );
}
