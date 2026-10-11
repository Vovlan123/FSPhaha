import { useState } from "react";
import { api } from "../../api";
import BlueprintView from "../../components/BlueprintView";
import { Empty, ErrorBox, Field, Loading, Modal, ReasonList, Salary, ScoreRing, StatusBadge, Tabs, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { ago } from "../../format";
import type { Application, Blueprint, Vacancy } from "../../types";

export default function CandidateVacancies() {
  const d = useDict();
  const [tab, setTab] = useState<"list" | "mine">("list");
  const [spec, setSpec] = useState("");
  const [q, setQ] = useState("");
  const vac = useLoad(
    () => api<Vacancy[]>(`/vacancies?${new URLSearchParams({ ...(spec ? { specialization: spec } : {}), ...(q ? { q } : {}) })}`),
    [spec, q],
  );
  const apps = useLoad(() => api<Application[]>("/candidate/applications"), []);
  const [applyTo, setApplyTo] = useState<Vacancy | null>(null);
  const [bpFor, setBpFor] = useState<Vacancy | null>(null);

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Вакансии</h1>
          <p>Основной путь — приглашения от работодателей. Если приглашений пока нет, проявите инициативу и откликнитесь сами: контакты увидит только эта компания.</p>
        </div>
      </div>
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[{ key: "list", label: "Все вакансии", count: vac.data?.length }, { key: "mine", label: "Мои отклики", count: apps.data?.length }]}
      />
      {tab === "list" && (
        <div className="stack">
          <div className="row">
            <select className="select" style={{ width: 240 }} value={spec} onChange={(e) => setSpec(e.target.value)} aria-label="Специализация">
              <option value="">Все специализации</option>
              {d.specializations.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
            <input className="input" style={{ maxWidth: 320 }} placeholder="Поиск по названию или компании" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <ErrorBox error={vac.error} />
          {vac.loading && !vac.data ? <Loading /> : (vac.data ?? []).length === 0 ? (
            <div className="card"><Empty title="Вакансий не найдено">Попробуйте изменить фильтр</Empty></div>
          ) : (
            (vac.data ?? []).map((v) => (
              <div key={v.id} className="card stack-sm">
                <div className="row-between" style={{ alignItems: "flex-start" }}>
                  <div className="stack-sm" style={{ flex: 1, minWidth: 260 }}>
                    <div className="row">
                      <h3>{v.title}</h3>
                      <span className="category">{v.category}</span>
                    </div>
                    <div className="small muted">
                      {v.company.name} · {v.city || "любой город"} · {v.work_format.map((f) => d.label(d.work_formats, f)).join(", ")} · {ago(v.created_at)}
                    </div>
                    <Salary from={v.salary_from} to={v.salary_to} large />
                    <p className="small">{v.description}</p>
                    <div className="chips">{v.stack_labels.map((s) => <span key={s} className="skill">{s}</span>)}</div>
                  </div>
                  {v.match && (
                    <div className="stack-sm" style={{ width: 300, maxWidth: "100%" }}>
                      <div className="row"><ScoreRing value={v.match.score} /><span className="small strong">соответствие вашему профилю</span></div>
                      <ReasonList reasons={v.match.reasons} limit={4} />
                    </div>
                  )}
                </div>
                <div className="row">
                  {v.application ? (
                    <span className="row small">Отклик отправлен <StatusBadge kind="application" status={v.application.status} /></span>
                  ) : (
                    <button className="btn btn-primary btn-sm" onClick={() => setApplyTo(v)}>Откликнуться</button>
                  )}
                  <button className="btn btn-ghost btn-sm" onClick={() => setBpFor(v)}>Какие задания проверяют эту вакансию</button>
                </div>
              </div>
            ))
          )}
        </div>
      )}
      {tab === "mine" && (
        <div className="card">
          <ErrorBox error={apps.error} />
          {(apps.data ?? []).length === 0 ? (
            <Empty title="Откликов пока нет">Откликнитесь на вакансию во вкладке «Все вакансии»</Empty>
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Вакансия</th><th>Компания</th><th>Зарплата</th><th>Отправлен</th><th>Статус</th></tr></thead>
                <tbody>
                  {(apps.data ?? []).map((a) => (
                    <tr key={a.id}>
                      <td className="strong">{a.vacancy.title}</td>
                      <td>{a.vacancy.company.name}</td>
                      <td><Salary from={a.vacancy.salary_from} to={a.vacancy.salary_to} /></td>
                      <td>{ago(a.created_at)}</td>
                      <td><StatusBadge kind="application" status={a.status} label={a.status_label} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
      {applyTo && (
        <ApplyModal
          v={applyTo}
          onClose={() => setApplyTo(null)}
          onDone={() => {
            setApplyTo(null);
            void vac.reload();
            void apps.reload();
          }}
        />
      )}
      {bpFor && <BlueprintModal v={bpFor} onClose={() => setBpFor(null)} />}
    </div>
  );
}

function ApplyModal({ v, onClose, onDone }: { v: Vacancy; onClose: () => void; onDone: () => void }) {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function send() {
    setBusy(true);
    setError(null);
    try {
      await api(`/vacancies/${v.id}/apply`, { body: { cover_letter: text } });
      toast("Отклик отправлен");
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={`Отклик: ${v.title}`}
      onClose={onClose}
      footer={<><button className="btn btn-ghost" onClick={onClose}>Отмена</button><button className="btn btn-primary" onClick={send} disabled={busy}>Отправить отклик</button></>}
    >
      <div className="stack">
        <div className="alert alert-warn small">После отклика компания «{v.company.name}» увидит ваши ФИО и контакты.</div>
        <Field label="Сопроводительное сообщение (необязательно)">
          <textarea className="textarea" value={text} onChange={(e) => setText(e.target.value)} maxLength={3000} />
        </Field>
        <ErrorBox error={error} />
      </div>
    </Modal>
  );
}

function BlueprintModal({ v, onClose }: { v: Vacancy; onClose: () => void }) {
  const bp = useLoad(() => api<Blueprint>(`/vacancies/${v.id}/blueprint`), [v.id]);
  return (
    <Modal title={`Задания под вакансию «${v.title}»`} onClose={onClose} wide>
      {bp.loading && !bp.data ? <Loading /> : bp.data ? <BlueprintView bp={bp.data} /> : <ErrorBox error={bp.error} />}
    </Modal>
  );
}
