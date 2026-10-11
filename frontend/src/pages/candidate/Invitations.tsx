import { useState } from "react";
import { api } from "../../api";
import { Empty, ErrorBox, Field, Loading, Modal, Salary, StatusBadge, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { ago, date, rub } from "../../format";
import type { Invitation } from "../../types";

export default function CandidateInvitations() {
  const list = useLoad(() => api<Invitation[]>("/candidate/invitations"), []);
  const [openId, setOpenId] = useState<number | null>(null);
  if (list.loading && !list.data) return <Loading />;
  if (list.error) return <ErrorBox error={list.error} />;
  const items = list.data ?? [];
  const active = items.filter((i) => i.status === "sent" || i.status === "viewed");
  const rest = items.filter((i) => !(i.status === "sent" || i.status === "viewed"));

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Приглашения</h1>
          <p>Работодатели нашли вас сами. Условия видны до начала общения, контакты откроются только после того, как вы примете приглашение.</p>
        </div>
      </div>
      {items.length === 0 ? (
        <div className="card">
          <Empty icon="✉" title="Приглашений пока нет">
            Повысьте силу профиля: привяжите ФСП ID и решайте регулярные задания. А пока можно откликнуться на вакансии самостоятельно.
          </Empty>
        </div>
      ) : (
        <>
          <Section title="Ждут ответа" items={active} onOpen={setOpenId} empty="Новых приглашений нет" />
          {rest.length > 0 && <Section title="Архив" items={rest} onOpen={setOpenId} />}
        </>
      )}
      {openId !== null && (
        <InvitationModal
          id={openId}
          onClose={() => setOpenId(null)}
          onChanged={(inv) => list.setData(items.map((x) => (x.id === inv.id ? inv : x)))}
        />
      )}
    </div>
  );
}

function Section({ title, items, onOpen, empty }: { title: string; items: Invitation[]; onOpen: (id: number) => void; empty?: string }) {
  return (
    <div className="stack">
      <h3>{title} <span className="muted">· {items.length}</span></h3>
      {items.length === 0 && empty && <p className="muted small">{empty}</p>}
      <div className="grid grid-2">
        {items.map((i) => (
          <button key={i.id} className="card card-link stack-sm" style={{ textAlign: "left" }} onClick={() => onOpen(i.id)}>
            <div className="row-between">
              <span className="strong">{i.company.name}</span>
              <StatusBadge kind="invitation" status={i.status} />
            </div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>{i.title}</div>
            <Salary from={i.salary_from} to={i.salary_to} large />
            <div className="row" style={{ gap: 6 }}>
              {i.trust?.company_verified
                ? <span className="badge badge-green">✓ Компания подтверждена</span>
                : <span className="badge badge-grey">Компания не подтверждена</span>}
              {i.below_expectations && <span className="badge badge-amber">Ниже ваших ожиданий</span>}
              {i.trust && i.trust.warnings.length > 0 && <span className="badge badge-amber">⚠ {i.trust.warnings.length}</span>}
            </div>
            <div className="tiny muted">
              {ago(i.created_at)}{i.status === "sent" || i.status === "viewed" ? ` · ответить до ${date(i.expires_at)}` : ""}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

function InvitationModal({ id, onClose, onChanged }: { id: number; onClose: () => void; onChanged: (i: Invitation) => void }) {
  const d = useDict();
  const inv = useLoad(() => api<Invitation>(`/candidate/invitations/${id}`), [id]);
  const [declining, setDeclining] = useState(false);
  const [complaining, setComplaining] = useState(false);
  const [complaintReason, setComplaintReason] = useState("fake");
  const [reason, setReason] = useState("salary");
  const [comment, setComment] = useState("");
  const [expected, setExpected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function act(path: string, body?: unknown) {
    setBusy(true);
    setError(null);
    try {
      const r = await api<Invitation>(`/candidate/invitations/${id}/${path}`, { method: "POST", body });
      inv.setData(r);
      onChanged(r);
      setDeclining(false);
      setComplaining(false);
      toast(path === "accept" ? "Приглашение принято — работодатель получил ваши контакты"
        : path === "complain" ? "Жалоба отправлена — спасибо, это помогает очищать платформу" : "Приглашение отклонено");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const i = inv.data;
  const open = i && (i.status === "sent" || i.status === "viewed");
  return (
    <Modal
      title={i ? i.title : "Приглашение"}
      onClose={() => {
        if (i) onChanged(i);
        onClose();
      }}
      footer={
        complaining ? (
          <>
            <button className="btn btn-ghost" onClick={() => setComplaining(false)}>Назад</button>
            <button className="btn btn-danger" disabled={busy} onClick={() => act("complain", { reason: complaintReason, comment: comment || null })}>
              Отправить жалобу
            </button>
          </>
        ) : open && !declining ? (
          <>
            <button className="btn btn-danger" onClick={() => setDeclining(true)} disabled={busy}>Отклонить</button>
            <button className="btn btn-success" onClick={() => act("accept")} disabled={busy}>Принять и открыть контакты</button>
          </>
        ) : declining ? (
          <>
            <button className="btn btn-ghost" onClick={() => setDeclining(false)}>Назад</button>
            <button
              className="btn btn-danger"
              disabled={busy}
              onClick={() => act("decline", { reason, comment: comment || null, expected_salary: reason === "salary" && expected ? Number(expected) : null })}
            >
              Отклонить приглашение
            </button>
          </>
        ) : undefined
      }
    >
      {inv.loading && !i ? <Loading /> : !i ? <ErrorBox error={inv.error} /> : (
        <div className="stack">
          <div className="row-between">
            <div>
              <div className="strong">{i.company.name}</div>
              <div className="tiny muted">{d.label(d.industries, i.company.industry)} · {i.company.city}</div>
            </div>
            <StatusBadge kind="invitation" status={i.status} />
          </div>
          <div className="card card-accent card-tight">
            <div className="small muted">Зарплата</div>
            <Salary from={i.salary_from} to={i.salary_to} large />
            {i.below_expectations && <div className="small" style={{ color: "var(--amber)", marginTop: 4 }}>Верхняя граница ниже ваших ожиданий</div>}
          </div>
          <p style={{ whiteSpace: "pre-wrap" }}>{i.description}</p>
          <dl className="kv">
            <dt>Формат</dt><dd>{i.work_format.map((f) => d.label(d.work_formats, f)).join(", ") || "—"}</dd>
            <dt>О компании</dt><dd className="small">{i.company.description || "—"}</dd>
            <dt>Срок ответа</dt><dd>{date(i.expires_at)}</dd>
          </dl>
          {i.trust && (
            <div className="card card-tight stack-sm" style={{ background: "var(--brand-50)" }}>
              <div className="row-between">
                <span className="strong small">Надёжность работодателя</span>
                {i.trust.company_verified
                  ? <span className="badge badge-green">✓ ИНН и домен подтверждены</span>
                  : <span className="badge badge-amber">Компания не подтверждена</span>}
              </div>
              <div className="small muted">
                {i.trust.accept_rate !== null
                  ? `Кандидаты приняли ${Math.round(i.trust.accept_rate * 100)}% ответов на приглашения компании за 90 дней (приглашений: ${i.trust.invitations_90d}).`
                  : "Статистики ответов на приглашения компании пока нет."}
              </div>
              {i.trust.warnings.length > 0 && (
                <ul className="reasons">
                  {i.trust.warnings.map((w) => <li key={w} className="minus"><span className="mark" aria-hidden>!</span><span>{w}</span></li>)}
                </ul>
              )}
            </div>
          )}
          {i.complaint_at && (
            <div className="alert alert-warn small">
              Вы пожаловались: {d.label(d.complaint_reasons, i.complaint_reason)}. Модератор проверит компанию; при нескольких жалобах её приглашения приостанавливаются.
            </div>
          )}
          {!i.complaint_at && !complaining && !declining && (
            <button className="btn btn-ghost btn-sm" style={{ alignSelf: "flex-start" }} onClick={() => setComplaining(true)}>
              Пожаловаться на приглашение
            </button>
          )}
          {complaining && (
            <div className="stack">
              <Field label="Что не так с приглашением?" hint="Работодатель не увидит, кто пожаловался. Если приглашение ещё открыто, оно будет отклонено">
                <select className="select" value={complaintReason} onChange={(e) => setComplaintReason(e.target.value)}>
                  {d.complaint_reasons.map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
                </select>
              </Field>
              <Field label="Комментарий (необязательно)">
                <textarea className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={1000} />
              </Field>
            </div>
          )}
          {i.status === "accepted" && (
            <div className="alert alert-success">
              <span>Вы приняли приглашение. Работодатель видит ваши контакты. Связаться с ним: <b>{i.contact_method}</b></span>
            </div>
          )}
          {i.status === "declined" && (
            <div className="alert alert-info">
              Отклонено: {i.decline_reason_label}{i.expected_salary ? `, ожидания ${rub(i.expected_salary)}` : ""}
            </div>
          )}
          {open && !declining && <div className="small muted">Способ связи с работодателем: {i.contact_method}. Ваши контакты откроются ему только после принятия.</div>}
          {declining && (
            <div className="stack">
              <Field label="Причина отказа" hint="Работодатель увидит причину — это помогает ему точнее делать предложения">
                <select className="select" value={reason} onChange={(e) => setReason(e.target.value)}>
                  {d.decline_reasons.map((r) => <option key={r.code} value={r.code}>{r.label}</option>)}
                </select>
              </Field>
              {reason === "salary" && (
                <Field label="Какая зарплата была бы интересна, ₽/мес">
                  <input className="input" type="number" min={1000} step={5000} value={expected} onChange={(e) => setExpected(e.target.value)} />
                </Field>
              )}
              <Field label="Комментарий (необязательно)">
                <textarea className="textarea" value={comment} onChange={(e) => setComment(e.target.value)} maxLength={1000} />
              </Field>
            </div>
          )}
          <ErrorBox error={error} />
        </div>
      )}
    </Modal>
  );
}
