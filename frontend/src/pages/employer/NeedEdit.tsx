import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../../api";
import SalaryFields, { parseRub, salaryError } from "../../components/SalaryFields";
import { ChipSelect, ErrorBox, Field, Loading, toast } from "../../components/ui";
import { useDict } from "../../dict";
import { salaryRange } from "../../format";
import type { Need, ParsedNeed } from "../../types";
import { CompanyGate } from "./common";

type Form = {
  title: string;
  description: string;
  team_about: string;
  specialization: string;
  grade: string;
  stack_must: string[];
  stack_nice: string[];
  work_format: string[];
  city: string;
  salary_from: string;
  salary_to: string;
};

const EMPTY: Form = {
  title: "", description: "", team_about: "", specialization: "", grade: "", stack_must: [], stack_nice: [],
  work_format: [], city: "", salary_from: "", salary_to: "",
};

type Recognized = Partial<Record<"specialization" | "grade" | "stack" | "work_format" | "salary", boolean>>;

const GRADE_SOURCE: Record<string, string> = { keyword: "по названию грейда в тексте", experience: "по требуемому стажу" };

/** Заголовок по первой фразе описания, если работодатель его не задал. */
function guessTitle(text: string): string {
  const first = text.trim().split(/[.!?\n]/)[0]?.trim() ?? "";
  return first.length > 120 ? `${first.slice(0, 117)}…` : first;
}

/** Поле с отметкой «распознано» после разбора описания. */
function RField({ label, rec, error, hint, children }: { label: string; rec?: boolean; error?: string | null; hint?: ReactNode; children: ReactNode }) {
  return (
    <div className={`field ${rec ? "recognized" : ""}`}>
      <div className="field-label">
        <span>{label}</span>
        {rec && <span className="rec-badge">✓ распознано</span>}
      </div>
      {children}
      {error ? <span className="error">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

function NeedForm() {
  const d = useDict();
  const nav = useNavigate();
  const { id } = useParams();
  const editId = id ? Number(id) : null;

  const [form, setForm] = useState<Form>(EMPTY);
  const [loading, setLoading] = useState(editId !== null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [parsing, setParsing] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsed, setParsed] = useState<ParsedNeed | null>(null);
  const [recognized, setRecognized] = useState<Recognized>({});
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (editId === null) return;
    api<Need>(`/employer/needs/${editId}`)
      .then((n) =>
        setForm({
          title: n.title, description: n.description, team_about: n.team_about, specialization: n.specialization, grade: n.grade,
          stack_must: n.stack_must, stack_nice: n.stack_nice, work_format: n.work_format, city: n.city,
          salary_from: String(n.salary_from), salary_to: String(n.salary_to),
        }),
      )
      .catch((e: Error) => setLoadError(e.message))
      .finally(() => setLoading(false));
  }, [editId]);

  const patch = (p: Partial<Form>) => setForm((f) => ({ ...f, ...p }));
  const spec = d.specializations.find((s) => s.code === form.specialization);

  // Варианты стека: справочник выбранной специализации + уже выбранные и распознанные навыки вне его
  const skillOptions = useMemo(() => {
    const base = spec?.skills ?? [];
    const extra = [...form.stack_must, ...form.stack_nice].filter((s) => !base.includes(s));
    return [...base, ...Array.from(new Set(extra))].map((code) => ({
      code,
      label: base.includes(code) ? d.skill(code) : `${d.skill(code)} · вне специализации`,
    }));
  }, [spec, form.stack_must, form.stack_nice, d]);

  async function parse() {
    setParsing(true);
    setParseError(null);
    try {
      const r = await api<ParsedNeed>("/employer/needs/parse", { body: { text: text.trim() } });
      const rec: Recognized = {};
      const next: Form = { ...form };
      if (r.specialization) { next.specialization = r.specialization; rec.specialization = true; }
      if (r.grade) { next.grade = r.grade; rec.grade = true; }
      if (r.stack_must.length || r.stack_nice.length) {
        next.stack_must = r.stack_must;
        next.stack_nice = r.stack_nice.filter((s) => !r.stack_must.includes(s));
        rec.stack = true;
      }
      if (r.work_format.length) { next.work_format = r.work_format; rec.work_format = true; }
      if (r.salary_from || r.salary_to) {
        next.salary_from = r.salary_from ? String(r.salary_from) : next.salary_from;
        next.salary_to = r.salary_to ? String(r.salary_to) : next.salary_to;
        rec.salary = true;
      }
      if (!next.description.trim()) next.description = text.trim().slice(0, 8000);
      if (!next.title.trim()) next.title = guessTitle(text);
      setForm(next);
      setRecognized(rec);
      setParsed(r);
    } catch (e) {
      setParseError((e as Error).message);
    } finally {
      setParsing(false);
    }
  }

  const errs = {
    title: form.title.trim().length < 3 ? "Название не короче 3 символов" : null,
    specialization: form.specialization ? null : "Выберите специализацию",
    grade: form.grade ? null : "Выберите грейд",
    salary: salaryError(form.salary_from, form.salary_to),
  };
  const valid = !errs.title && !errs.specialization && !errs.grade && !errs.salary;

  async function save() {
    setTried(true);
    setSaveError(null);
    if (!valid) return;
    setBusy(true);
    try {
      const body = {
        title: form.title.trim(), description: form.description.trim(), team_about: form.team_about.trim(),
        specialization: form.specialization, grade: form.grade, stack_must: form.stack_must, stack_nice: form.stack_nice,
        work_format: form.work_format, city: form.city.trim(),
        salary_from: parseRub(form.salary_from), salary_to: parseRub(form.salary_to),
      };
      const n = editId
        ? await api<Need>(`/employer/needs/${editId}`, { method: "PUT", body })
        : await api<Need>("/employer/needs", { body });
      toast(editId ? "Потребность обновлена, подборка пересчитана" : "Потребность сохранена, подборка сформирована");
      nav(`/employer/needs/${n.id}`);
    } catch (e) {
      setSaveError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading) return <Loading />;
  if (loadError) return <ErrorBox error={loadError} />;

  const notRecognized = parsed
    ? [
        !parsed.specialization && "специализация",
        !parsed.grade && "грейд",
        !parsed.stack_must.length && !parsed.stack_nice.length && "стек",
        !parsed.work_format.length && "формат работы",
        !parsed.salary_from && !parsed.salary_to && "зарплатная вилка",
      ].filter(Boolean)
    : [];

  return (
    <div className="stack-lg" style={{ maxWidth: 920 }}>
      <div className="page-head">
        <div>
          <Link to={editId ? `/employer/needs/${editId}` : "/employer/needs"} className="small">← {editId ? "К подборке" : "К потребностям"}</Link>
          <h1 style={{ marginTop: 6 }}>{editId ? "Уточнить потребность" : "Новая потребность"}</h1>
          <p>
            {editId
              ? "После сохранения подборка пересчитается: шорт-лист сохранится, новые кандидаты получат метку «новый»."
              : "Опишите задачу своими словами или вставьте текст вакансии — система разберёт его и заполнит поля."}
          </p>
        </div>
      </div>

      <div className="card card-accent stack">
        <Field label="Опишите, кого ищете" hint="Например: «Ищем Middle Python-разработчика в команду платежей. PostgreSQL, Kafka, Docker обязательно, Redis будет плюсом. Удалёнка или гибрид, 250–330 тыс.»">
          <textarea
            className="textarea"
            style={{ minHeight: 150 }}
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={20000}
            placeholder="Задачи, команда, обязательный и желательный стек, опыт, формат работы, зарплата…"
          />
        </Field>
        <div className="row">
          <button className="btn btn-primary" onClick={parse} disabled={parsing || text.trim().length < 10}>
            {parsing ? "Разбираем…" : "Разобрать описание"}
          </button>
          {!text.trim() && (
            <button type="button" className="btn btn-ghost" onClick={() => setText(EXAMPLE_NEED)}>
              Подставить пример
            </button>
          )}
          {text.trim().length > 0 && text.trim().length < 10 && <span className="small muted">Нужно хотя бы 10 символов</span>}
        </div>
        <ErrorBox error={parseError} />
        {parsed && (
          <div className="alert alert-success">
            <span aria-hidden>✓</span>
            <div className="stack-sm">
              <div>
                <b>Распознано:</b>{" "}
                {[
                  parsed.specialization && `специализация ${d.spec(parsed.specialization)}`,
                  parsed.grade && `грейд ${d.grade(parsed.grade)}${parsed.grade_source && GRADE_SOURCE[parsed.grade_source] ? ` (${GRADE_SOURCE[parsed.grade_source]})` : ""}`,
                  parsed.stack_must.length > 0 && `обязательный стек: ${parsed.stack_must.map(d.skill).join(", ")}`,
                  parsed.stack_nice.length > 0 && `желательный: ${parsed.stack_nice.map(d.skill).join(", ")}`,
                  parsed.work_format.length > 0 && `формат: ${parsed.work_format.map((f) => d.label(d.work_formats, f)).join(", ")}`,
                  parsed.salary_from && parsed.salary_to ? `вилка ${salaryRange(parsed.salary_from, parsed.salary_to)}` : null,
                ]
                  .filter(Boolean)
                  .join("; ") || "ничего"}
                .
              </div>
              {notRecognized.length > 0 && <div>Не найдено в тексте: {notRecognized.join(", ")} — заполните вручную.</div>}
              {parsed.outside_specialization && parsed.outside_specialization.length > 0 && (
                <div>
                  Навыки вне справочника специализации: {parsed.outside_specialization.map(d.skill).join(", ")} — оставлены в стеке,
                  проверьте, нужны ли они.
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="card stack">
        <h3>Потребность</h3>
        <Field label="Название *" error={tried ? errs.title : null}>
          <input className={`input ${tried && errs.title ? "invalid" : ""}`} value={form.title} maxLength={200}
            onChange={(e) => patch({ title: e.target.value })} placeholder="Например, бэкенд платёжного шлюза" />
        </Field>
        <Field label="Описание задач" hint="Используется для текстовой близости с профилями кандидатов">
          <textarea className="textarea" value={form.description} maxLength={8000} onChange={(e) => patch({ description: e.target.value })} />
        </Field>
        <Field label="О команде">
          <textarea className="textarea" style={{ minHeight: 70 }} value={form.team_about} maxLength={4000}
            onChange={(e) => patch({ team_about: e.target.value })} placeholder="Состав команды, процессы, релизы" />
        </Field>

        <RField label="Специализация *" rec={recognized.specialization} error={tried ? errs.specialization : null} hint={spec?.description}>
          <select className="select" value={form.specialization} onChange={(e) => patch({ specialization: e.target.value })}>
            <option value="">Выберите специализацию</option>
            {d.specializations.map((s) => <option key={s.code} value={s.code}>{s.label}</option>)}
          </select>
        </RField>

        <RField label="Грейд *" rec={recognized.grade} error={tried ? errs.grade : null}>
          <div className="grid grid-4" style={{ gap: 10 }} role="radiogroup" aria-label="Грейд">
            {d.grades.map((g) => (
              <button
                key={g.code}
                type="button"
                role="radio"
                aria-checked={form.grade === g.code}
                className={`pick ${form.grade === g.code ? "on" : ""}`}
                onClick={() => patch({ grade: g.code })}
              >
                <div className="row-between"><span className="t">{g.label}</span><span className="tiny muted">{g.years}</span></div>
                <div className="tiny muted" style={{ marginTop: 4 }}>{g.description}</div>
              </button>
            ))}
          </div>
        </RField>

        <RField
          label="Обязательный стек"
          rec={recognized.stack}
          hint={spec ? "Навык, подтверждённый тестом, весит больше заявленного" : "Сначала выберите специализацию — появится справочник навыков"}
        >
          <ChipSelect
            options={skillOptions}
            value={form.stack_must}
            onChange={(v) => patch({ stack_must: v, stack_nice: form.stack_nice.filter((s) => !v.includes(s)) })}
          />
        </RField>
        <RField label="Желательный стек" rec={recognized.stack} hint="Даёт дополнительные баллы, но не обязателен">
          <ChipSelect
            options={skillOptions.filter((o) => !form.stack_must.includes(o.code))}
            value={form.stack_nice}
            onChange={(v) => patch({ stack_nice: v })}
          />
        </RField>

        <div className="grid grid-2">
          <RField label="Формат работы" rec={recognized.work_format} hint="Не выбрано — подойдёт любой">
            <ChipSelect options={d.work_formats} value={form.work_format} onChange={(v) => patch({ work_format: v })} />
          </RField>
          <Field label="Город" hint="Для удалённого формата город не учитывается">
            <input className="input" value={form.city} maxLength={100} onChange={(e) => patch({ city: e.target.value })} placeholder="Москва" />
          </Field>
        </div>

        <div className={`field ${recognized.salary ? "recognized" : ""}`}>
          {recognized.salary && <span className="rec-badge" style={{ alignSelf: "flex-start" }}>✓ вилка распознана</span>}
          <SalaryFields
            from={form.salary_from}
            to={form.salary_to}
            onFrom={(v) => patch({ salary_from: v })}
            onTo={(v) => patch({ salary_to: v })}
            showError={tried}
          />
        </div>

        <ErrorBox error={saveError} />
        <div className="row">
          <button className="btn btn-primary btn-lg" onClick={save} disabled={busy}>
            {busy ? "Сохраняем и подбираем…" : editId ? "Сохранить и пересчитать подборку" : "Сохранить и получить подборку"}
          </button>
          <Link to={editId ? `/employer/needs/${editId}` : "/employer/needs"} className="btn btn-ghost">Отмена</Link>
        </div>
      </div>
    </div>
  );
}

const EXAMPLE_NEED =
  "Ищем Middle Python-разработчика в команду платёжного шлюза: приём платежей, возвраты, сверки с банками. " +
  "Обязательно: Python, PostgreSQL, Kafka, Docker, опыт от 2 лет. Будет плюсом Redis и Kubernetes. " +
  "Формат — удалёнка или гибрид, офис в Москве. Зарплата 250 000 – 330 000 ₽.";

export default function NeedEdit() {
  return (
    <CompanyGate>
      <NeedForm />
    </CompanyGate>
  );
}
