import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import InviteModal from "../../components/InviteModal";
import { Bar, ChipSelect, Empty, ErrorBox, Field, Loading, Modal, StatusBadge, Switch, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { dateShort, pct } from "../../format";
import type { Assignment, RegularTask } from "../../types";
import { CompanyGate, isActiveInvitation } from "./common";

const KINDS: { code: RegularTask["kind"]; label: string; hint: string }[] = [
  { code: "approach", label: "Предложить подход", hint: "Кандидат описывает решение словами: архитектура, шаги, риски" },
  { code: "solve", label: "Решить", hint: "Кандидат присылает решение: код, запрос, расчёт" },
];
const kindLabel = (k: string) => KINDS.find((x) => x.code === k)?.label ?? k;

type RubricRow = { point: string; keywords: string };

function TaskFormModal({ onClose, onSaved }: { onClose: () => void; onSaved: () => void }) {
  const d = useDict();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [kind, setKind] = useState<RegularTask["kind"]>("approach");
  const [specialization, setSpecialization] = useState("");
  const [grades, setGrades] = useState<string[]>([]);
  const [rubric, setRubric] = useState<RubricRow[]>([{ point: "", keywords: "" }]);
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const splitKeywords = (s: string) => s.split(",").map((k) => k.trim()).filter(Boolean);
  // Полностью пустые строки рубрики игнорируем, частично заполненные — ошибка
  const filled = rubric.filter((r) => r.point.trim() || r.keywords.trim());
  const rubricRowError = (r: RubricRow) =>
    !r.point.trim() && !r.keywords.trim()
      ? null
      : r.point.trim().length < 2
        ? "Сформулируйте пункт"
        : splitKeywords(r.keywords).length === 0
          ? "Нужно хотя бы одно ключевое слово"
          : null;
  const errs = {
    title: title.trim().length < 3 ? "Название не короче 3 символов" : null,
    body: body.trim().length < 10 ? "Опишите задание (не короче 10 символов)" : null,
    specialization: specialization ? null : "Выберите специализацию",
    rubric: filled.length === 0 ? "Добавьте хотя бы один пункт рубрики" : filled.some((r) => rubricRowError(r)) ? "Исправьте пункты рубрики" : null,
  };
  const valid = !errs.title && !errs.body && !errs.specialization && !errs.rubric;

  const setRow = (i: number, p: Partial<RubricRow>) => setRubric((rows) => rows.map((r, j) => (j === i ? { ...r, ...p } : r)));

  async function save() {
    setTried(true);
    setError(null);
    if (!valid) return;
    setBusy(true);
    try {
      await api("/employer/tasks", {
        body: {
          title: title.trim(), body: body.trim(), kind, specialization, grades,
          rubric: filled.map((r) => ({ point: r.point.trim(), keywords: splitKeywords(r.keywords) })),
        },
      });
      toast("Задание создано — система начнёт выдавать его кандидатам");
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
      title="Новое регулярное задание"
      onClose={onClose}
      wide
      footer={
        <>
          <button className="btn btn-secondary" onClick={onClose} disabled={busy}>Отмена</button>
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? "Сохраняем…" : "Создать задание"}</button>
        </>
      }
    >
      <div className="stack">
        <Field label="Название *" error={tried ? errs.title : null}>
          <input className={`input ${tried && errs.title ? "invalid" : ""}`} value={title} maxLength={200} onChange={(e) => setTitle(e.target.value)}
            placeholder="Например, идемпотентность платёжного API" />
        </Field>
        <Field label="Условие *" error={tried ? errs.body : null} hint="Короткая задача на 15–30 минут">
          <textarea className="textarea" value={body} maxLength={8000} onChange={(e) => setBody(e.target.value)} />
        </Field>
        <div className="field">
          <label>Тип задания</label>
          <div className="grid grid-2" style={{ gap: 10 }} role="radiogroup" aria-label="Тип задания">
            {KINDS.map((k) => (
              <button key={k.code} type="button" role="radio" aria-checked={kind === k.code} className={`pick ${kind === k.code ? "on" : ""}`} onClick={() => setKind(k.code)}>
                <div className="t">{k.label}</div>
                <div className="tiny muted" style={{ marginTop: 2 }}>{k.hint}</div>
              </button>
            ))}
          </div>
        </div>
        <div className="grid grid-2">
          <Field label="Специализация *" error={tried ? errs.specialization : null}>
            <select className="select" value={specialization} onChange={(e) => setSpecialization(e.target.value)}>
              <option value="">Выберите</option>
              {d.specializations.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
            </select>
          </Field>
          <Field label="Грейды" hint="Не выбрано — задание получат кандидаты всех грейдов">
            <ChipSelect options={d.grades} value={grades} onChange={setGrades} />
          </Field>
        </div>

        <div className="field">
          <label>Рубрика автооценки *</label>
          <span className="hint">
            Ключевые пункты хорошего ответа. Пункт засчитывается, если в ответе встречается любое из ключевых слов — можно
            писать основы слов: «транзакц» найдёт «транзакция» и «транзакции».
          </span>
          <div className="stack-sm" style={{ marginTop: 6 }}>
            {rubric.map((r, i) => {
              const rowErr = tried ? rubricRowError(r) : null;
              return (
                <div key={i}>
                  <div className="rubric-row">
                    <input className={`input ${rowErr ? "invalid" : ""}`} value={r.point} maxLength={300} placeholder={`Пункт ${i + 1}: что должно быть в ответе`}
                      onChange={(e) => setRow(i, { point: e.target.value })} aria-label={`Пункт ${i + 1}`} />
                    <input className={`input ${rowErr ? "invalid" : ""}`} value={r.keywords} placeholder="ключевые слова через запятую"
                      onChange={(e) => setRow(i, { keywords: e.target.value })} aria-label={`Ключевые слова пункта ${i + 1}`} />
                    <button type="button" className="btn btn-ghost btn-sm" disabled={rubric.length === 1}
                      onClick={() => setRubric((rows) => rows.filter((_, j) => j !== i))} aria-label={`Удалить пункт ${i + 1}`}>
                      Удалить
                    </button>
                  </div>
                  {rowErr && <span className="tiny" style={{ color: "var(--red)" }}>{rowErr}</span>}
                </div>
              );
            })}
          </div>
          <div style={{ marginTop: 6 }}>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => setRubric((rows) => [...rows, { point: "", keywords: "" }])}>
              + Добавить пункт
            </button>
          </div>
          {tried && errs.rubric && <span className="error">{errs.rubric}</span>}
        </div>
        <ErrorBox error={error} />
      </div>
    </Modal>
  );
}

function Submissions({ task }: { task: RegularTask }) {
  const { data, error, loading, setData } = useLoad(
    () => api<{ task: RegularTask; submissions: Assignment[] }>(`/employer/tasks/${task.id}/submissions`),
    [task.id],
  );
  const [rating, setRating] = useState<number | null>(null);
  const [inviting, setInviting] = useState<Assignment | null>(null);

  const patchSub = (id: number, p: Partial<Assignment>) =>
    setData((prev) => prev && { ...prev, submissions: prev.submissions.map((s) => (s.id === id ? { ...s, ...p } : s)) });

  async function rate(a: Assignment, score: number) {
    setRating(a.id);
    try {
      const updated = await api<Assignment>(`/employer/submissions/${a.id}/rate`, { body: { score } });
      patchSub(a.id, { employer_score: updated.employer_score });
      toast(`Оценка ${score} из 5 сохранена`);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setRating(null);
    }
  }

  if (loading && !data) return <Loading />;
  if (!data) return <ErrorBox error={error} />;
  if (data.submissions.length === 0) return <Empty icon="✎" title="Решений пока нет">Задание выдаётся кандидатам подходящей специализации и грейда.</Empty>;

  const points = data.task.rubric.map((r) => r.point);
  return (
    <div className="stack">
      <p className="small muted">Решения анонимны: видны код кандидата и категория. Оценка 1–5 учитывается в активности кандидата.</p>
      {data.submissions.map((a) => {
        const c = a.candidate;
        const inv = a.invitation;
        return (
          <div key={a.id} className="card card-tight stack-sm" style={{ boxShadow: "none" }}>
            <div className="row-between">
              <div className="row" style={{ gap: 8 }}>
                {c ? <Link to={`/employer/candidates/${c.id}`} className="strong">Кандидат {c.anon_code}</Link> : <span className="strong">Кандидат</span>}
                {c?.category && <span className="category">{c.category}</span>}
                <span className="tiny muted">решено {dateShort(a.submitted_at)}</span>
              </div>
              {inv && <span className="small">Приглашение: <StatusBadge kind="invitation" status={inv.status} /></span>}
            </div>
            <div className="answer">{a.answer}</div>
            <div className="grid grid-2" style={{ alignItems: "start" }}>
              <div className="stack-sm">
                <div className="row-between small"><span className="strong">Автооценка по рубрике</span><span className="strong">{pct(a.auto_score)}</span></div>
                <Bar value={a.auto_score ?? 0} green />
                <ul className="reasons">
                  {points.map((p) => {
                    const hit = a.rubric_hits.includes(p);
                    return (
                      <li key={p} className={hit ? "plus" : "info"}>
                        <span className="mark" aria-hidden>{hit ? "✓" : "–"}</span>
                        <span className={hit ? "" : "muted"}>{p}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
              <div className="stack-sm" style={{ alignItems: "flex-start" }}>
                <span className="small strong">Ваша оценка</span>
                <div className="rate" role="group" aria-label="Оценка от 1 до 5">
                  {[1, 2, 3, 4, 5].map((n) => (
                    <button key={n} className={a.employer_score === n ? "on" : ""} onClick={() => rate(a, n)} disabled={rating === a.id}
                      aria-pressed={a.employer_score === n} title={`Оценка ${n}`}>
                      {n}
                    </button>
                  ))}
                </div>
                {c && !isActiveInvitation(inv?.status) && inv?.status !== "accepted" && (
                  <button className="btn btn-success btn-sm" onClick={() => setInviting(a)}>Пригласить автора</button>
                )}
              </div>
            </div>
          </div>
        );
      })}
      {inviting?.candidate && (
        <InviteModal
          candidate={{ id: inviting.candidate.id, display_name: `Кандидат ${inviting.candidate.anon_code}`, category: inviting.candidate.category }}
          onClose={() => setInviting(null)}
          onSent={(inv) => {
            // У одного кандидата может быть несколько решений — обновляем статус во всех
            const cid = inviting.candidate?.id;
            setData((prev) => prev && {
              ...prev,
              submissions: prev.submissions.map((s) => (s.candidate?.id === cid ? { ...s, invitation: { id: inv.id, status: inv.status } } : s)),
            });
          }}
        />
      )}
    </div>
  );
}

function TaskCard({ t, onToggle, toggling }: { t: RegularTask; onToggle: (v: boolean) => void; toggling: boolean }) {
  const d = useDict();
  const [open, setOpen] = useState(false);
  return (
    <div className="card stack-sm">
      <div className="row-between" style={{ alignItems: "flex-start" }}>
        <div className="stack-sm" style={{ minWidth: 0 }}>
          <div className="row" style={{ gap: 8 }}>
            <h3>{t.title}</h3>
            <span className="badge badge-blue">{kindLabel(t.kind)}</span>
            {!t.active && <span className="badge badge-grey">выдача выключена</span>}
          </div>
          <div className="cand-meta">
            <span>{d.spec(t.specialization)}</span>
            <span>{t.grades.length ? t.grades.map((g) => d.grade(g)).join(", ") : "все грейды"}</span>
            <span>создано {dateShort(t.created_at)}</span>
          </div>
        </div>
        <div style={{ minWidth: 260 }} className={toggling ? "emp-busy" : ""}>
          <Switch checked={t.active} onChange={onToggle} label="Выдавать кандидатам" hint={t.active ? "Задание участвует в выдаче" : "Новые кандидаты его не получат"} />
        </div>
      </div>
      <div className="grid grid-3" style={{ gap: 10 }}>
        <div className="stat"><span className="value">{t.assigned ?? 0}</span><span className="label">выдано</span></div>
        <div className="stat"><span className="value">{t.submitted ?? 0}</span><span className="label">решено</span></div>
        <div className="stat"><span className="value">{pct(t.avg_auto_score)}</span><span className="label">средняя автооценка</span></div>
      </div>
      <details className="why">
        <summary>Условие и рубрика ({t.rubric.length})</summary>
        <div className="stack-sm" style={{ marginTop: 8 }}>
          <p className="small" style={{ whiteSpace: "pre-wrap" }}>{t.body}</p>
          <ul className="small" style={{ margin: 0, paddingLeft: 20 }}>
            {t.rubric.map((r, i) => (
              <li key={i}><b>{r.point}</b> <span className="muted">— {r.keywords.join(", ")}</span></li>
            ))}
          </ul>
        </div>
      </details>
      <div className="row" style={{ marginTop: 4 }}>
        <button className={`btn btn-sm ${open ? "btn-primary" : "btn-secondary"}`} onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          {open ? "Скрыть решения" : `Решения (${t.submitted ?? 0})`}
        </button>
      </div>
      {open && <div style={{ marginTop: 8 }}><Submissions task={t} /></div>}
    </div>
  );
}

function TasksView() {
  const { data, error, loading, reload, setData } = useLoad(() => api<RegularTask[]>("/employer/tasks"));
  const [creating, setCreating] = useState(false);
  const [toggling, setToggling] = useState<number | null>(null);

  async function toggle(t: RegularTask, active: boolean) {
    setToggling(t.id);
    try {
      const updated = await api<RegularTask>(`/employer/tasks/${t.id}/active`, { body: { active } });
      setData((prev) => prev && prev.map((x) => (x.id === t.id ? { ...x, active: updated.active } : x)));
      toast(updated.active ? "Выдача задания включена" : "Выдача задания выключена");
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
          <h1>Регулярные задания</h1>
          <p>
            Короткие задачи с рубрикой: система выдаёт их кандидатам подходящей категории и оценивает ответы автоматически.
            Вы видите решения анонимно, ставите оценку и можете пригласить автора.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setCreating(true)}>Новое задание</button>
      </div>

      {data.length === 0 ? (
        <div className="card">
          <Empty icon="✎" title="Заданий пока нет">
            <p>Создайте короткое задание с рубрикой оценки — так вы увидите, как кандидаты рассуждают о ваших задачах.</p>
            <div style={{ marginTop: 14 }}>
              <button className="btn btn-primary" onClick={() => setCreating(true)}>Новое задание</button>
            </div>
          </Empty>
        </div>
      ) : (
        <div className="stack">
          {data.map((t) => <TaskCard key={t.id} t={t} onToggle={(v) => toggle(t, v)} toggling={toggling === t.id} />)}
        </div>
      )}

      {creating && <TaskFormModal onClose={() => setCreating(false)} onSaved={() => void reload()} />}
    </div>
  );
}

export default function EmployerTasks() {
  return (
    <CompanyGate>
      <TasksView />
    </CompanyGate>
  );
}
