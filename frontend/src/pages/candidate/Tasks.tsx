import { useState } from "react";
import { api, ApiError } from "../../api";
import { Empty, ErrorBox, Field, Loading, StatusBadge, toast, useLoad } from "../../components/ui";
import { date, dateShort, pct } from "../../format";
import type { Assignment } from "../../types";

type TasksResp = { current: Assignment | null; history: Assignment[]; next_task_at: string | null; interval_days: number };

export default function CandidateTasks() {
  const t = useLoad(() => api<TasksResp>("/candidate/tasks"), []);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(fn: () => Promise<unknown>, ok: string) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      toast(ok);
      setAnswer("");
      await t.reload();
    } catch (e) {
      const ae = e as ApiError;
      setError(ae.availableAt ? `${ae.message}: ${date(ae.availableAt)}` : ae.message);
    } finally {
      setBusy(false);
    }
  }

  if (t.loading && !t.data) return <Loading />;
  if (!t.data) return <ErrorBox error={t.error} />;
  const { current, history, next_task_at, interval_days } = t.data;

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Регулярные задания</h1>
          <p>
            Раз в {interval_days} дней система предлагает короткую задачу от работодателя: решить её или предложить подход.
            Результаты поддерживают профиль актуальным и дают работодателю свежий сигнал о вас.
          </p>
        </div>
      </div>
      <ErrorBox error={error} />
      {current?.task ? (
        <div className="card stack">
          <div className="row-between">
            <div>
              <div className="small muted">Задание от {current.task.company} · {current.task.kind === "solve" ? "решите задачу" : "предложите подход"}</div>
              <h2>{current.task.title}</h2>
            </div>
            <StatusBadge kind="assignment" status={current.status} />
          </div>
          <p style={{ whiteSpace: "pre-wrap" }}>{current.task.body}</p>
          <div className="alert alert-brand small">
            <span aria-hidden>ⓘ</span>
            <span>Что оценивается: {current.task.rubric_points.join("; ")}.</span>
          </div>
          <Field label="Ваш ответ" hint="5–10 предложений обычно достаточно">
            <textarea className="textarea" style={{ minHeight: 180 }} value={answer} onChange={(e) => setAnswer(e.target.value)} maxLength={8000} />
          </Field>
          <div className="row">
            <button className="btn btn-primary" disabled={busy || answer.trim().length < 10}
              onClick={() => run(() => api(`/candidate/tasks/${current.id}/submit`, { body: { answer } }), "Ответ отправлен")}>
              Отправить ответ
            </button>
            <button className="btn btn-ghost" disabled={busy}
              onClick={() => run(() => api(`/candidate/tasks/${current.id}/skip`, { method: "POST" }), "Задание пропущено")}>
              Пропустить
            </button>
          </div>
        </div>
      ) : (
        <div className="card card-accent row-between">
          <div>
            <h3>{next_task_at ? "Следующее задание скоро" : "Новое задание доступно"}</h3>
            <p className="small muted">{next_task_at ? `Будет доступно ${date(next_task_at)}` : "Задание подбирается под вашу специализацию и грейд."}</p>
          </div>
          <button className="btn btn-primary" disabled={busy || Boolean(next_task_at)}
            onClick={() => run(() => api("/candidate/tasks/next", { method: "POST" }), "Задание получено")}>
            Получить задание
          </button>
        </div>
      )}
      <div className="card">
        <h3 style={{ marginBottom: 10 }}>История</h3>
        {history.length === 0 ? <Empty title="Решённых заданий пока нет" /> : (
          <div className="stack">
            {history.map((a) => (
              <div key={a.id} className="card card-tight stack-sm">
                <div className="row-between">
                  <span className="strong">{a.task?.title}</span>
                  <div className="row">
                    {a.auto_score !== null && <span className="badge">автооценка {pct(a.auto_score)}</span>}
                    {a.employer_score && <span className="badge badge-green">работодатель: {a.employer_score}/5</span>}
                    <StatusBadge kind="assignment" status={a.status} />
                  </div>
                </div>
                <div className="tiny muted">{a.task?.company} · {dateShort(a.submitted_at ?? a.assigned_at)}</div>
                {a.answer && <p className="small" style={{ whiteSpace: "pre-wrap" }}>{a.answer}</p>}
                {a.rubric_hits.length > 0 && <div className="chips">{a.rubric_hits.map((h) => <span key={h} className="skill verified">✓ {h}</span>)}</div>}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
