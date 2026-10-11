import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, ApiError } from "../../api";
import { CodeBlock, ErrorBox, Loading, ThetaScale, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { date } from "../../format";
import type { Attempt, Availability, TestItem } from "../../types";

const LETTERS = "АБВГДЕЖЗ";

export default function TestRun() {
  const { id } = useParams();
  const att = useLoad(() => api<Attempt>(`/tests/${id}`), [id]);
  if (att.loading && !att.data) return <Loading />;
  if (att.error || !att.data) return <ErrorBox error={att.error} />;
  if (att.data.status === "in_progress" && att.data.current_item)
    return <Question attempt={att.data} item={att.data.current_item} onUpdate={att.setData} />;
  return <Result attempt={att.data} onUpdate={att.setData} />;
}

function useCountdown(item: TestItem) {
  // Отсчёт от момента выдачи вопроса сервером; итоговое время всё равно проверяет сервер
  const deadline = new Date(item.served_at).getTime() + item.time_limit_sec * 1000;
  const [left, setLeft] = useState(() => Math.max(0, Math.round((deadline - Date.now()) / 1000)));
  useEffect(() => {
    const t = window.setInterval(() => setLeft(Math.max(0, Math.round((deadline - Date.now()) / 1000))), 500);
    return () => window.clearInterval(t);
  }, [deadline]);
  return Math.min(left, item.time_limit_sec);
}

function Question({ attempt, item, onUpdate }: { attempt: Attempt; item: TestItem; onUpdate: (a: Attempt) => void }) {
  const d = useDict();
  const [choice, setChoice] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const left = useCountdown(item);
  const sent = useRef<number | null>(null);

  const submit = useCallback(
    async (idx: number) => {
      if (sent.current === item.id) return;
      sent.current = item.id;
      setBusy(true);
      setError(null);
      try {
        const next = await api<Attempt>(`/tests/${attempt.id}/answer`, { body: { item_id: item.id, answer_index: idx } });
        setChoice(null);
        onUpdate(next);
        window.scrollTo({ top: 0 });
      } catch (e) {
        sent.current = null;
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    },
    [attempt.id, item.id, onUpdate],
  );

  useEffect(() => {
    if (left === 0) void submit(choice ?? -1); // время вышло — отправляем выбранное или «нет ответа»
  }, [left, choice, submit]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const n = Number(e.key);
      if (n >= 1 && n <= item.options.length) setChoice(n - 1);
      if (e.key === "Enter" && choice !== null && !busy) void submit(choice);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [item.options.length, choice, busy, submit]);

  const mm = Math.floor(left / 60);
  const ss = String(left % 60).padStart(2, "0");
  const plain = item.options.every((o) => /[а-яё]/i.test(o) && o.length > 25);
  return (
    <div className="stack" style={{ maxWidth: 860, margin: "0 auto" }}>
      <div className="row-between">
        <div>
          <div className="small muted">Тест: {d.spec(attempt.specialization)} · заявленный грейд {d.grade(attempt.declared_grade)}</div>
          <h2>Вопрос {item.order}</h2>
        </div>
        <span className={`timer ${left <= 20 ? "low" : ""}`} aria-live="polite" aria-label={`Осталось ${left} секунд`}>{mm}:{ss}</span>
      </div>
      <div>
        <div className="bar"><span style={{ width: `${Math.min(100, (attempt.answered / attempt.max_items) * 100)}%` }} /></div>
        <div className="tiny muted" style={{ marginTop: 4 }}>
          Отвечено {attempt.answered}. Тест адаптивный и заканчивается, когда результат статистически уверенный: обычно {attempt.min_items}–{attempt.max_items} вопросов.
        </div>
      </div>
      <div className="card stack">
        {item.topic_labels.length > 0 && (
          <div className="chips">{item.topic_labels.map((t) => <span key={t} className="skill">{t}</span>)}</div>
        )}
        <div className="strong" style={{ fontSize: 16 }}>{item.stem}</div>
        {item.code && <CodeBlock code={item.code} lang={item.code_lang} />}
        <div className="options" role="radiogroup" aria-label="Варианты ответа">
          {item.options.map((o, i) => (
            <button
              key={i}
              type="button"
              role="radio"
              aria-checked={choice === i}
              className={`option ${choice === i ? "selected" : ""}`}
              onClick={() => setChoice(i)}
            >
              <span className="letter">{LETTERS[i]}</span>
              <span className={`text ${plain ? "plain" : ""}`}>{o}</span>
            </button>
          ))}
        </div>
        <ErrorBox error={error} />
        <div className="row-between">
          <span className="tiny muted">Клавиши 1–{item.options.length} — выбор, Enter — ответить. Вернуться к вопросу нельзя.</span>
          <button className="btn btn-primary btn-lg" disabled={choice === null || busy} onClick={() => choice !== null && submit(choice)}>
            {busy ? "Отправляем…" : "Ответить"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Trace({ attempt }: { attempt: Attempt }) {
  // Траектория оценки θ после каждого ответа — показывает, как адаптивный тест сходится
  const pts = attempt.trace ?? [];
  if (pts.length < 2) return null;
  const W = 520, H = 120, min = -3, max = 3;
  const x = (i: number) => 20 + (i / (pts.length - 1)) * (W - 40);
  const y = (t: number) => H - 10 - ((Math.max(min, Math.min(max, t)) - min) / (max - min)) * (H - 20);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label="Траектория оценки уровня по ходу теста" style={{ maxWidth: W }}>
      <polygon
        points={[
          ...pts.map((p, i) => `${x(i)},${y(p.theta + p.se)}`),
          ...pts.map((p, i) => `${x(i)},${y(p.theta - p.se)}`).reverse(),
        ].join(" ")}
        fill="var(--brand-100)"
      />
      <polyline points={pts.map((p, i) => `${x(i)},${y(p.theta)}`).join(" ")} fill="none" stroke="var(--brand-600)" strokeWidth={2.5} />
      {pts.map((p, i) => (
        <circle key={i} cx={x(i)} cy={y(p.theta)} r={4.5} fill={p.is_correct ? "var(--green)" : "var(--red)"}>
          <title>{`Вопрос ${p.order}: ${p.is_correct ? "верно" : "неверно"}, θ = ${p.theta.toFixed(2)}`}</title>
        </circle>
      ))}
    </svg>
  );
}

function Result({ attempt, onUpdate }: { attempt: Attempt; onUpdate: (a: Attempt) => void }) {
  const d = useDict();
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const av = useLoad(() => api<Availability[]>("/tests/availability"), [attempt.id, attempt.upgrade_accepted]);
  const confirmed = attempt.result === "confirmed" || attempt.result === "confirmed_plus";
  const grade = attempt.upgrade_accepted && attempt.upgrade_grade ? attempt.upgrade_grade : attempt.declared_grade;
  const suggested = attempt.suggested_grade ? av.data?.find((a) => a.grade === attempt.suggested_grade) : undefined;

  async function acceptUpgrade() {
    setBusy(true);
    try {
      onUpdate(await api<Attempt>(`/tests/${attempt.id}/accept-upgrade`, { method: "POST" }));
      toast("Грейд повышен");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function retake(g: string) {
    setBusy(true);
    try {
      const a = await api<Attempt>("/tests/start", { body: { declared_grade: g } });
      nav(`/candidate/test/${a.id}`);
      onUpdate(a);
    } catch (e) {
      const ae = e as ApiError;
      setError(ae.availableAt ? `${ae.message}. Доступно с ${date(ae.availableAt)}` : ae.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack-lg" style={{ maxWidth: 900, margin: "0 auto" }}>
      <div className={`card ${confirmed ? "hero-card" : ""}`}>
        <div className="stack">
          <span className={`badge ${confirmed ? "badge-solid" : "badge-red"}`} style={{ alignSelf: "flex-start", background: confirmed ? "rgba(255,255,255,.2)" : undefined }}>
            {attempt.status === "abandoned" ? "Тест прерван" : d.status("result", attempt.result ?? "")}
          </span>
          {confirmed ? (
            <>
              <h1>Ваша категория: {d.specShort(attempt.specialization)} · {d.grade(grade)}</h1>
              <p className="muted">Работодатели видят категорию и подтверждённые темы. Контакты — только после вашего согласия на приглашение.</p>
            </>
          ) : (
            <>
              <h1>Грейд {d.grade(attempt.declared_grade)} пока не подтверждён</h1>
              <p className="muted">
                Грейд не понижается принудительно. Можно сразу пройти тест на уровень ниже — результат уже показывает
                {attempt.suggested_grade ? ` уровень «${d.grade(attempt.suggested_grade)}»` : " более низкий уровень"}.
                Повторить тест на {d.grade(attempt.declared_grade)} можно через 30 дней.
              </p>
            </>
          )}
        </div>
      </div>
      <ErrorBox error={error} />
      {attempt.result === "confirmed_plus" && !attempt.upgrade_accepted && attempt.upgrade_grade && (
        <div className="alert alert-success row-between">
          <span>Вы ответили уверенно — результат выше порога грейда «{d.grade(attempt.upgrade_grade)}». Можно сразу принять повышение (в течение 7 дней).</span>
          <button className="btn btn-success btn-sm" disabled={busy} onClick={acceptUpgrade}>Принять {d.grade(attempt.upgrade_grade)}</button>
        </div>
      )}
      {attempt.result === "not_confirmed" && attempt.suggested_grade && (
        <div className="alert alert-info row-between">
          <span>Рекомендуем тест на «{d.grade(attempt.suggested_grade)}».{suggested && !suggested.allowed ? ` ${suggested.reason}` : ""}</span>
          <button className="btn btn-primary btn-sm" disabled={busy || (suggested ? !suggested.allowed : false)} onClick={() => retake(attempt.suggested_grade!)}>
            Пройти тест на {d.grade(attempt.suggested_grade)}
          </button>
        </div>
      )}
      <div className="grid grid-2">
        <div className="card stack">
          <h3>Оценка уровня</h3>
          {attempt.theta !== undefined && <ThetaScale theta={attempt.theta} se={attempt.se} highlight={confirmed ? grade : null} />}
          <div className="grid grid-3">
            <div className="stat"><span className="value">{attempt.n_items}</span><span className="label">вопросов</span></div>
            <div className="stat"><span className="value">{attempt.correct}</span><span className="label">верных</span></div>
            <div className="stat"><span className="value">±{attempt.se?.toFixed(2)}</span><span className="label">точность θ</span></div>
          </div>
          <div className="tiny muted">
            Оценка θ — по модели IRT 2PL с учётом сложности каждого задания, поэтому два кандидата с разными наборами вопросов сравнимы.
            {attempt.timed_out ? ` Без ответа по времени: ${attempt.timed_out}.` : ""}
          </div>
        </div>
        <div className="card stack">
          <h3>Как тест сходился</h3>
          <Trace attempt={attempt} />
          <div className="tiny muted">Точки — ответы (зелёные верные, красные неверные), линия — оценка уровня после каждого ответа, заливка — погрешность.</div>
        </div>
      </div>
      {attempt.topics && attempt.topics.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: 4 }}>Темы теста</h3>
          <p className="tiny muted" style={{ marginBottom: 10 }}>
            Вопросы подбираются под ваш уровень, поэтому сравниваем не долю верных, а результат с ожиданием модели для вашего θ.
          </p>
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Тема</th><th>Верно</th><th>Ожидалось для вашего уровня</th><th>Статус</th></tr></thead>
              <tbody>
                {attempt.topics.map((t) => (
                  <tr key={t.topic}>
                    <td className="strong">{t.label}</td>
                    <td>{t.correct} из {t.total}</td>
                    <td className="muted">{t.expected.toFixed(1)}</td>
                    <td>
                      {t.status === "verified" ? <span className="badge badge-green">✓ подтверждено</span>
                        : t.status === "refuted" ? <span className="badge badge-red">слабее остальных</span>
                        : <span className="badge badge-grey">мало данных</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
      <div className="row">
        <Link to="/candidate" className="btn btn-primary">В личный кабинет</Link>
        <Link to="/candidate/grade" className="btn btn-secondary">История тестов</Link>
      </div>
    </div>
  );
}
