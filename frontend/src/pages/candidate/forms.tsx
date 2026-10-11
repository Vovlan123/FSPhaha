import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../../api";
import { ChipSelect, Field, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { date } from "../../format";
import type { Attempt, Availability, CandidateProfile } from "../../types";

export type ResumeHints = { specialization: string | null; stack: string[]; experience_years: number | null; grade_guess: string | null };

type Parsed = {
  full_name: string | null; contact_email: string | null; phone: string | null; telegram: string | null; city: string | null;
  specialization: string | null; stack: string[]; stack_labels: string[]; experience_years: number | null; grade_guess: string | null;
  roles: string[]; soft_skills: string[]; about: string;
};

/** Шаг 1: профиль вручную или из PDF-резюме с автораспознаванием (поля можно поправить перед сохранением). */
export function ProfileForm({ profile, onSaved, onHints, submitLabel = "Сохранить и продолжить" }: {
  profile: CandidateProfile; onSaved: (p: CandidateProfile) => void; onHints?: (h: ResumeHints) => void; submitLabel?: string;
}) {
  const d = useDict();
  const [f, setF] = useState({
    full_name: profile.full_name, phone: profile.phone, telegram: profile.telegram, contact_email: profile.contact_email || profile.email,
    city: profile.city, relocation: profile.relocation, about: profile.about, experience_years: profile.experience_years,
    roles: profile.roles, soft_skills: profile.soft_skills, resume_source: profile.resume_source as "form" | "pdf",
  });
  const [recognized, setRecognized] = useState<string[]>([]);
  const [parseInfo, setParseInfo] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof typeof f>(k: K, v: (typeof f)[K]) => setF((x) => ({ ...x, [k]: v }));

  async function upload(file: File) {
    setError(null);
    setParseInfo("Распознаём резюме…");
    const form = new FormData();
    form.append("file", file);
    try {
      const p = await api<Parsed>("/candidate/resume/parse", { form });
      const got: string[] = [];
      setF((x) => {
        const n = { ...x, resume_source: "pdf" as const };
        if (p.full_name) { n.full_name = p.full_name; got.push("ФИО"); }
        if (p.contact_email) { n.contact_email = p.contact_email; got.push("email"); }
        if (p.phone) { n.phone = p.phone; got.push("телефон"); }
        if (p.telegram) { n.telegram = p.telegram; got.push("Telegram"); }
        if (p.city) { n.city = p.city; got.push("город"); }
        if (p.experience_years !== null) { n.experience_years = p.experience_years; got.push("стаж"); }
        if (p.roles.length) { n.roles = p.roles; got.push("роли"); }
        if (p.soft_skills.length) { n.soft_skills = p.soft_skills; got.push("софт-скиллы"); }
        if (p.about) { n.about = p.about; got.push("о себе"); }
        return n;
      });
      setRecognized(got);
      setParseInfo(
        `Распознано: ${got.join(", ") || "—"}. Стек (${p.stack_labels.length}): ${p.stack_labels.join(", ") || "—"} — подставим его в опрос. Проверьте поля перед сохранением.`,
      );
      onHints?.({ specialization: p.specialization, stack: p.stack, experience_years: p.experience_years, grade_guess: p.grade_guess });
    } catch (e) {
      setParseInfo(null);
      setError((e as Error).message);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<CandidateProfile>("/candidate/profile", { method: "PUT", body: { ...f, experience_years: Number(f.experience_years) || 0 } }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const mark = (k: string) => (recognized.includes(k) ? " ✓" : "");
  return (
    <form className="stack" onSubmit={submit}>
      <div className="card card-accent card-tight row-between">
        <div>
          <div className="strong">Есть резюме в PDF?</div>
          <div className="small muted">Загрузите — поля заполнятся автоматически. Пример: docs/samples/resume_sample.pdf</div>
        </div>
        <label className="btn btn-secondary">
          Загрузить PDF
          <input type="file" accept="application/pdf" hidden onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
        </label>
      </div>
      {parseInfo && <div className="alert alert-success">{parseInfo}</div>}
      <div className="grid grid-2">
        <Field label={`ФИО${mark("ФИО")}`} hint="Работодатель увидит имя только после принятия приглашения">
          <input className="input" required value={f.full_name} onChange={(e) => set("full_name", e.target.value)} />
        </Field>
        <Field label={`Город${mark("город")}`}>
          <input className="input" value={f.city} onChange={(e) => set("city", e.target.value)} />
        </Field>
        <Field label={`Email для связи${mark("email")}`}>
          <input className="input" type="email" value={f.contact_email} onChange={(e) => set("contact_email", e.target.value)} />
        </Field>
        <Field label={`Телефон${mark("телефон")}`}>
          <input className="input" value={f.phone} onChange={(e) => set("phone", e.target.value)} />
        </Field>
        <Field label={`Telegram${mark("Telegram")}`}>
          <input className="input" value={f.telegram} onChange={(e) => set("telegram", e.target.value)} placeholder="@username" />
        </Field>
        <Field label={`Коммерческий стаж, лет${mark("стаж")}`}>
          <input className="input" type="number" min={0} max={60} step={0.5} value={f.experience_years} onChange={(e) => set("experience_years", Number(e.target.value))} />
        </Field>
      </div>
      <label className="check">
        <input type="checkbox" checked={f.relocation} onChange={(e) => set("relocation", e.target.checked)} />
        <span>Готов(а) к переезду</span>
      </label>
      <Field label={`Роли в команде${mark("роли")}`}>
        <ChipSelect options={d.roles} value={f.roles} onChange={(v) => set("roles", v)} />
      </Field>
      <Field label={`Софт-скиллы${mark("софт-скиллы")}`}>
        <ChipSelect options={d.soft_skills} value={f.soft_skills} onChange={(v) => set("soft_skills", v)} />
      </Field>
      <Field label={`О себе${mark("о себе")}`} hint="Пара предложений о задачах, которые вам интересны">
        <textarea className="textarea" value={f.about} onChange={(e) => set("about", e.target.value)} maxLength={4000} />
      </Field>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="row"><button className="btn btn-primary" disabled={busy}>{busy ? "Сохраняем…" : submitLabel}</button></div>
    </form>
  );
}

/** Шаг 2: опрос по отрасли и специализации. */
export function SurveyForm({ profile, hints, onSaved, submitLabel = "Сохранить и выбрать грейд" }: {
  profile: CandidateProfile; hints?: ResumeHints | null; onSaved: (p: CandidateProfile) => void; submitLabel?: string;
}) {
  const d = useDict();
  const [spec, setSpec] = useState<string>(profile.specialization ?? hints?.specialization ?? "");
  const allowedFor = (s: string) => d.specializations.find((x) => x.code === s)?.skills ?? [];
  const [stack, setStack] = useState<string[]>(
    profile.stack.length ? profile.stack : (hints?.stack ?? []).filter((s) => allowedFor(spec).includes(s)),
  );
  const [industries, setIndustries] = useState<string[]>(profile.industries);
  const [exp, setExp] = useState<number>(profile.experience_years || hints?.experience_years || 0);
  const [formats, setFormats] = useState<string[]>(profile.work_format.length ? profile.work_format : ["remote"]);
  const [salary, setSalary] = useState<string>(profile.salary_expect_min ? String(profile.salary_expect_min) : "");
  const [city, setCity] = useState(profile.city);
  const [relocation, setRelocation] = useState(profile.relocation);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const changingSpec = Boolean(profile.grade && profile.specialization && spec !== profile.specialization);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!spec) return setError("Выберите специализацию");
    if (!stack.length) return setError("Отметьте хотя бы один навык");
    if (!formats.length) return setError("Выберите формат работы");
    if (!salary || Number(salary) < 1000) return setError("Укажите минимальные ожидания по зарплате");
    setBusy(true);
    setError(null);
    try {
      onSaved(await api<CandidateProfile>("/candidate/survey", {
        body: { specialization: spec, stack, industries, experience_years: exp, work_format: formats, salary_expect_min: Number(salary), city, relocation },
      }));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="stack" onSubmit={submit}>
      <Field label="Специализация">
        <div className="grid grid-3">
          {d.specializations.map((s) => (
            <button
              type="button"
              key={s.code}
              className={`card card-tight card-link ${spec === s.code ? "card-accent" : ""}`}
              style={{ textAlign: "left", borderColor: spec === s.code ? "var(--brand-500)" : undefined }}
              aria-pressed={spec === s.code}
              onClick={() => {
                setSpec(s.code);
                setStack((cur) => cur.filter((x) => s.skills.includes(x)).concat((hints?.stack ?? []).filter((x) => s.skills.includes(x) && !cur.includes(x))));
              }}
            >
              <div className="strong">{s.label}</div>
              <div className="tiny muted">{s.description}</div>
            </button>
          ))}
        </div>
      </Field>
      {changingSpec && (
        <div className="alert alert-warn">Смена специализации меняет категорию: грейд нужно будет подтвердить заново, и это возможно только после окончания периода смены грейда.</div>
      )}
      {spec && (
        <Field label="Стек" hint="Отмечайте то, чем реально пользуетесь: навыки из стека получат приоритет в тесте, а подтверждённые тестом будут выделены для работодателя">
          <ChipSelect options={allowedFor(spec).map((s) => ({ code: s, label: d.skill(s) }))} value={stack} onChange={setStack} />
        </Field>
      )}
      <Field label="Интересные отрасли">
        <ChipSelect options={d.industries} value={industries} onChange={setIndustries} />
      </Field>
      <div className="grid grid-3">
        <Field label="Коммерческий стаж, лет">
          <input className="input" type="number" min={0} max={60} step={0.5} value={exp} onChange={(e) => setExp(Number(e.target.value))} />
        </Field>
        <Field label="Зарплата от, ₽/мес" hint="Работодатель увидит, укладывается ли его вилка">
          <input className="input" type="number" min={1000} step={5000} value={salary} onChange={(e) => setSalary(e.target.value)} placeholder="200000" />
        </Field>
        <Field label="Город">
          <input className="input" value={city} onChange={(e) => setCity(e.target.value)} />
        </Field>
      </div>
      <Field label="Формат работы">
        <ChipSelect options={d.work_formats} value={formats} onChange={setFormats} />
      </Field>
      <label className="check">
        <input type="checkbox" checked={relocation} onChange={(e) => setRelocation(e.target.checked)} />
        <span>Готов(а) к переезду</span>
      </label>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="row"><button className="btn btn-primary" disabled={busy}>{busy ? "Сохраняем…" : submitLabel}</button></div>
    </form>
  );
}

/** Шаг 3: выбор предполагаемого грейда и старт адаптивного теста. */
export function GradePicker({ currentGrade, suggested }: { currentGrade: string | null; suggested?: string | null }) {
  const d = useDict();
  const nav = useNavigate();
  const av = useLoad(() => api<Availability[]>("/tests/availability"), []);
  const [grade, setGrade] = useState<string | null>(suggested ?? null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    if (!grade) return;
    setBusy(true);
    setError(null);
    try {
      const att = await api<Attempt>("/tests/start", { body: { declared_grade: grade } });
      nav(`/candidate/test/${att.id}`);
    } catch (e) {
      const ae = e as ApiError;
      setError(ae.availableAt ? `${ae.message}. Доступно с ${date(ae.availableAt)}` : ae.message);
    } finally {
      setBusy(false);
    }
  }

  const byGrade = Object.fromEntries((av.data ?? []).map((a) => [a.grade, a]));
  return (
    <div className="stack">
      <div className="grid grid-2">
        {d.grades.map((g) => {
          const a = byGrade[g.code];
          const disabled = a ? !a.allowed : false;
          const on = grade === g.code;
          return (
            <button
              key={g.code}
              type="button"
              disabled={disabled}
              onClick={() => setGrade(g.code)}
              aria-pressed={on}
              className={`card card-tight card-link ${on ? "card-accent" : ""}`}
              style={{ textAlign: "left", borderColor: on ? "var(--brand-500)" : undefined, opacity: disabled ? 0.55 : 1, cursor: disabled ? "not-allowed" : "pointer" }}
            >
              <div className="row-between">
                <span className="strong">{g.label}</span>
                <span className="badge badge-grey">{g.years}</span>
              </div>
              <div className="small muted" style={{ marginTop: 4 }}>{g.description}</div>
              {currentGrade === g.code && <div className="badge badge-green" style={{ marginTop: 6 }}>Ваш текущий грейд</div>}
              {suggested === g.code && currentGrade !== g.code && <div className="badge" style={{ marginTop: 6 }}>Рекомендуем</div>}
              {disabled && a?.reason && (
                <div className="tiny" style={{ marginTop: 6, color: "var(--red)" }}>
                  {a.reason}{a.available_at ? ` · доступно с ${date(a.available_at)}` : ""}
                </div>
              )}
            </button>
          );
        })}
      </div>
      <div className="alert alert-brand">
        <span aria-hidden>ⓘ</span>
        <span className="small">
          Тест адаптивный: 10–20 вопросов, следующий подбирается по вашим ответам. На вопрос — 2 минуты, вернуться к
          предыдущему нельзя. Грейд не понижается принудительно: если заявленный не подтвердится, можно сразу пройти тест
          на грейд ниже, а повторить этот — через 30 дней. Сменить подтверждённый грейд можно раз в 90 дней.
        </span>
      </div>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="row">
        <button className="btn btn-primary btn-lg" disabled={!grade || busy} onClick={start}>
          {busy ? "Готовим тест…" : grade ? `Начать тест на ${d.grade(grade)}` : "Выберите грейд"}
        </button>
      </div>
    </div>
  );
}
