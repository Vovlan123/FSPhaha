import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { Empty, ErrorBox, Loading, Salary, StatusBadge, Tabs, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { dateShort, rub } from "../../format";
import type { Invitation, Quota } from "../../types";
import { CompanyGate, isActiveInvitation } from "./common";

type TabKey = "all" | "sent" | "viewed" | "accepted" | "declined" | "expired" | "withdrawn";
const STATUSES: Exclude<TabKey, "all">[] = ["sent", "viewed", "accepted", "declined", "expired", "withdrawn"];

function CandidateResponse({ inv }: { inv: Invitation }) {
  const contacts = inv.candidate?.contacts;
  if (inv.status === "accepted" && contacts) {
    const tg = contacts.telegram?.replace(/^@/, "");
    return (
      <div className="contacts-box stack-sm">
        <div className="strong">{contacts.full_name || "Контакты кандидата"}</div>
        {contacts.email && <div><a href={`mailto:${contacts.email}`}>{contacts.email}</a></div>}
        {contacts.phone && <div><a href={`tel:${contacts.phone}`}>{contacts.phone}</a></div>}
        {tg && <div><a href={`https://t.me/${tg}`} target="_blank" rel="noreferrer">@{tg}</a></div>}
      </div>
    );
  }
  if (inv.status === "declined") {
    return (
      <div className="stack-sm small">
        <span className="strong">{inv.decline_reason_label ?? "Причина не указана"}</span>
        {inv.decline_comment && <div className="quote">{inv.decline_comment}</div>}
        {inv.expected_salary && <span>Ожидает от <b>{rub(inv.expected_salary)}</b></span>}
      </div>
    );
  }
  if (isActiveInvitation(inv.status)) return <span className="small muted">ответ до {dateShort(inv.expires_at)}</span>;
  return <span className="muted small">—</span>;
}

function InvitationsView() {
  const d = useDict();
  const { data, error, loading, setData } = useLoad(() =>
    Promise.all([api<Invitation[]>("/employer/invitations"), api<Quota>("/employer/invitations/quota")]),
  );
  const [tab, setTab] = useState<TabKey>("all");
  const [withdrawing, setWithdrawing] = useState<number | null>(null);

  async function withdraw(inv: Invitation) {
    if (!window.confirm(`Отозвать приглашение «${inv.title}»? Кандидат больше не сможет его принять.`)) return;
    setWithdrawing(inv.id);
    try {
      const updated = await api<Invitation>(`/employer/invitations/${inv.id}/withdraw`, { method: "POST" });
      setData((prev) => prev && [prev[0].map((x) => (x.id === inv.id ? updated : x)), prev[1]]);
      toast("Приглашение отозвано");
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setWithdrawing(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;

  const [list, quota] = data;
  const counts = Object.fromEntries(STATUSES.map((s) => [s, list.filter((i) => i.status === s).length]));
  const tabs = [
    { key: "all" as TabKey, label: "Все", count: list.length },
    ...STATUSES.map((s) => ({ key: s as TabKey, label: d.status("invitation", s), count: counts[s] })),
  ];
  const shown = tab === "all" ? list : list.filter((i) => i.status === tab);

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Приглашения</h1>
          <p>Контакты кандидата открываются, когда он принимает приглашение. При отказе видна причина и ожидаемая зарплата.</p>
        </div>
        <div className="card card-tight stat" style={{ minWidth: 220 }}>
          <span className="value">{quota.left} <span className="small muted">из {quota.limit}</span></span>
          <span className="label">приглашений осталось на неделе</span>
        </div>
      </div>

      <div className="card">
        <Tabs tabs={tabs} value={tab} onChange={setTab} />
        {shown.length === 0 ? (
          <Empty icon="✉" title={tab === "all" ? "Приглашений пока нет" : "В этом статусе приглашений нет"}>
            {tab === "all" && (
              <p>
                Пригласите кандидата из <Link to="/employer/needs">подборки</Link> или <Link to="/employer/bank">банка кандидатов</Link>.
              </p>
            )}
          </Empty>
        ) : (
          <div className="table-wrap">
            <table className="table" style={{ minWidth: 900 }}>
              <thead>
                <tr>
                  <th>Кандидат</th><th>Позиция</th><th>Вилка</th><th>Создано</th><th>Статус</th><th>Ответ кандидата</th><th />
                </tr>
              </thead>
              <tbody>
                {shown.map((inv) => (
                  <tr key={inv.id} style={inv.status === "accepted" ? { background: "#f6fcf8" } : undefined}>
                    <td>
                      {inv.candidate ? (
                        <>
                          <Link to={`/employer/candidates/${inv.candidate.id}`} className="strong">{inv.candidate.display_name}</Link>
                          <div className="tiny muted">{inv.candidate.category ?? "—"}</div>
                        </>
                      ) : "—"}
                    </td>
                    <td>
                      <div>{inv.title}</div>
                      {inv.need_id && <Link to={`/employer/needs/${inv.need_id}`} className="tiny">по потребности</Link>}
                      {inv.work_format.length > 0 && (
                        <div className="tiny muted">{inv.work_format.map((f) => d.label(d.work_formats, f)).join(", ")}</div>
                      )}
                    </td>
                    <td>
                      <Salary from={inv.salary_from} to={inv.salary_to} />
                      {inv.below_expectations && (
                        <div style={{ marginTop: 4 }}><span className="badge badge-amber" title="Верхняя граница ниже ожиданий кандидата">ниже ожиданий</span></div>
                      )}
                    </td>
                    <td className="small nowrap">{dateShort(inv.created_at)}</td>
                    <td>
                      <StatusBadge kind="invitation" status={inv.status} label={inv.status_label} />
                      {inv.responded_at ? (
                        <div className="tiny muted" style={{ marginTop: 4 }}>ответ {dateShort(inv.responded_at)}</div>
                      ) : inv.viewed_at ? (
                        <div className="tiny muted" style={{ marginTop: 4 }}>открыто {dateShort(inv.viewed_at)}</div>
                      ) : null}
                    </td>
                    <td style={{ minWidth: 200 }}><CandidateResponse inv={inv} /></td>
                    <td>
                      {isActiveInvitation(inv.status) && (
                        <button className="btn btn-danger btn-sm" onClick={() => withdraw(inv)} disabled={withdrawing === inv.id}>
                          {withdrawing === inv.id ? "Отзываем…" : "Отозвать"}
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

export default function EmployerInvitations() {
  return (
    <CompanyGate>
      <InvitationsView />
    </CompanyGate>
  );
}
