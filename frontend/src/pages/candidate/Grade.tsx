import { Link } from "react-router-dom";
import { api } from "../../api";
import { ErrorBox, Loading, StatusBadge, ThetaScale, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { date, dateShort } from "../../format";
import type { Attempt, CandidateStatus } from "../../types";
import { GradePicker } from "./forms";

type History = {
  surveys: { id: number; created_at: string; answers: Record<string, unknown> }[];
  attempts: Attempt[];
  grade_events: { from_grade: string | null; to_grade: string; reason: string; attempt_id: number | null; created_at: string }[];
};

const REASON: Record<string, string> = { test: "по тесту", upgrade: "повышение по уверенному результату", lower_test: "тест на грейд ниже" };

export default function GradePage() {
  const d = useDict();
  const data = useLoad(async () => {
    const [status, history] = await Promise.all([api<CandidateStatus>("/candidate/status"), api<History>("/candidate/history")]);
    return { status, history };
  }, []);
  if (data.loading && !data.data) return <Loading />;
  if (data.error || !data.data) return <ErrorBox error={data.error} />;
  const { status: s, history: h } = data.data;

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Грейд и тесты</h1>
          <p>Текущий статус, история опросов и попыток. Сменить грейд можно в обе стороны, но не чаще раза в 90 дней.</p>
        </div>
        <Link to="/candidate/profile" className="btn btn-secondary">Пройти опрос заново</Link>
      </div>

      <div className="grid grid-2">
        <div className="card stack">
          <h3>Текущий статус</h3>
          <dl className="kv">
            <dt>Специализация</dt><dd>{d.spec(s.specialization)}</dd>
            <dt>Грейд</dt><dd>{s.grade_label ?? "не подтверждён"}</dd>
            <dt>Категория</dt><dd>{s.category ? <span className="category">{s.category}</span> : "—"}</dd>
            <dt>Подтверждён</dt><dd>{date(s.grade_changed_at)}</dd>
            <dt>Следующая смена</dt><dd>{s.next_grade_change_at ? `не раньше ${date(s.next_grade_change_at)}` : "доступна"}</dd>
          </dl>
          {s.theta !== null && <ThetaScale theta={s.theta} se={s.theta_se} highlight={s.grade} />}
        </div>
        <div className="card stack">
          <h3>Пройти тест на другой грейд</h3>
          <GradePicker currentGrade={s.grade} />
        </div>
      </div>

      <div className="card">
        <h3 style={{ marginBottom: 10 }}>Попытки теста</h3>
        {h.attempts.length === 0 ? (
          <p className="muted small">Попыток пока нет</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Дата</th><th>Заявленный грейд</th><th>Вопросов</th><th>θ</th><th>Итог</th><th /></tr></thead>
              <tbody>
                {h.attempts.map((a) => (
                  <tr key={a.id}>
                    <td>{dateShort(a.started_at)}</td>
                    <td>{d.specShort(a.specialization)} · {d.grade(a.declared_grade)}</td>
                    <td>{a.n_items ?? a.answered}</td>
                    <td className="mono">{a.theta !== undefined && a.theta !== null ? `${a.theta.toFixed(2)} ± ${a.se?.toFixed(2)}` : "—"}</td>
                    <td>
                      {a.status === "in_progress" ? <StatusBadge kind="attempt" status="in_progress" /> : <StatusBadge kind="result" status={a.result ?? ""} />}
                      {a.upgrade_accepted && <span className="badge badge-green" style={{ marginLeft: 6 }}>повышен до {d.grade(a.upgrade_grade)}</span>}
                    </td>
                    <td className="right"><Link to={`/candidate/test/${a.id}`} className="small">{a.status === "in_progress" ? "Продолжить" : "Подробнее"}</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="grid grid-2">
        <div className="card">
          <h3 style={{ marginBottom: 10 }}>Изменения грейда</h3>
          {h.grade_events.length === 0 ? <p className="muted small">Пока нет</p> : (
            <ul className="stack-sm small" style={{ margin: 0, paddingLeft: 18 }}>
              {h.grade_events.map((e, i) => (
                <li key={i}>
                  {dateShort(e.created_at)}: {e.from_grade ? `${d.grade(e.from_grade)} → ` : ""}<b>{d.grade(e.to_grade)}</b> <span className="muted">({REASON[e.reason] ?? e.reason})</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="card">
          <h3 style={{ marginBottom: 10 }}>История опросов</h3>
          {h.surveys.length === 0 ? <p className="muted small">Пока нет</p> : (
            <ul className="stack-sm small" style={{ margin: 0, paddingLeft: 18 }}>
              {h.surveys.map((sv) => (
                <li key={sv.id}>
                  {dateShort(sv.created_at)}: {d.spec(String(sv.answers.specialization))}, стек: {((sv.answers.stack as string[]) ?? []).map(d.skill).join(", ")}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
