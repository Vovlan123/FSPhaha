import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../../api";
import { Empty, ErrorBox, Field, Loading, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { dateShort } from "../../format";
import type { EmployerCompany, Integrations } from "../../types";
import { markCompanyComplete } from "./common";

const SIZES = ["1–10", "11–50", "51–200", "200–500", "500–1000", "1000+"];

type Form = {
  name: string;
  description: string;
  industry: string;
  website: string;
  city: string;
  size: string;
  contact_email: string;
  contact_telegram: string;
  contact_phone: string;
  inn: string;
};

const EMPTY: Form = { name: "", description: "", industry: "", website: "", city: "", size: "", contact_email: "", contact_telegram: "", contact_phone: "", inn: "" };

export default function CompanyPage() {
  const d = useDict();
  const nav = useNavigate();
  const { data, error, loading, setData } = useLoad(() => api<EmployerCompany>("/employer/company"));
  const [form, setForm] = useState<Form>(EMPTY);
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    if (!data) return;
    setForm({
      name: data.name, description: data.description, industry: data.industry, website: data.website, city: data.city,
      size: data.size, contact_email: data.contact_email, contact_telegram: data.contact_telegram, contact_phone: data.contact_phone,
      inn: data.inn ?? "",
    });
  }, [data]);

  const set = (k: keyof Form) => (e: { target: { value: string } }) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const nameError = form.name.trim().length < 2 ? "Укажите название компании (не короче 2 символов)" : null;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setTried(true);
    setSaveError(null);
    if (nameError) return;
    setBusy(true);
    const wasComplete = data?.complete;
    try {
      const saved = await api<EmployerCompany>("/employer/company", {
        method: "PUT",
        body: Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v.trim()])),
      });
      setData(saved);
      markCompanyComplete();
      toast("Профиль компании сохранён");
      if (!wasComplete) nav("/employer");
    } catch (err) {
      setSaveError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox error={error} />;
  if (!data) return null;

  const sizes = form.size && !SIZES.includes(form.size) ? [form.size, ...SIZES] : SIZES;

  return (
    <div className="stack-lg" style={{ maxWidth: 820 }}>
      <div className="page-head">
        <div>
          <h1>Профиль компании</h1>
          <p>Кандидаты видят название, отрасль и описание вместе с приглашением — от этого зависит, примут ли его.</p>
        </div>
      </div>

      {!data.complete && (
        <div className="alert alert-brand">
          <span aria-hidden>ⓘ</span>
          <span>Заполните название компании — после этого откроются подбор, банк кандидатов и приглашения.</span>
        </div>
      )}

      <form className="card stack" onSubmit={submit} noValidate>
        <h3>О компании</h3>
        <Field label="Название *" error={tried ? nameError : null}>
          <input className={`input ${tried && nameError ? "invalid" : ""}`} value={form.name} onChange={set("name")} maxLength={200} placeholder="ООО «Цифровые решения»" />
        </Field>
        <Field label="Описание" hint="Чем занимается компания, какие команды и продукты">
          <textarea className="textarea" value={form.description} onChange={set("description")} maxLength={4000} />
        </Field>
        <div className="grid grid-2">
          <Field label="Отрасль">
            <select className="select" value={form.industry} onChange={set("industry")}>
              <option value="">Не указана</option>
              {d.industries.map((i) => <option key={i.code} value={i.code}>{i.label}</option>)}
            </select>
          </Field>
          <Field label="Размер компании">
            <select className="select" value={form.size} onChange={set("size")}>
              <option value="">Не указан</option>
              {sizes.map((s) => <option key={s} value={s}>{s} сотрудников</option>)}
            </select>
          </Field>
          <Field label="Сайт">
            <input className="input" value={form.website} onChange={set("website")} maxLength={255} placeholder="https://company.ru" />
          </Field>
          <Field label="Город">
            <input className="input" value={form.city} onChange={set("city")} maxLength={100} placeholder="Москва" />
          </Field>
          <Field label="ИНН" hint="10 цифр для юрлица, 12 — для ИП. Нужен для подтверждения компании">
            <input className="input mono" inputMode="numeric" value={form.inn} onChange={set("inn")} maxLength={12} placeholder="7701234567" />
          </Field>
        </div>

        <div className="divider" />
        <div>
          <h3>Контакты для кандидатов</h3>
          <p className="small muted" style={{ marginTop: 4 }}>Подставляются в поле «Способ связи» при отправке приглашения.</p>
        </div>
        <div className="grid grid-3">
          <Field label="Email">
            <input className="input" type="email" value={form.contact_email} onChange={set("contact_email")} maxLength={255} placeholder="hr@company.ru" />
          </Field>
          <Field label="Telegram">
            <input className="input" value={form.contact_telegram} onChange={set("contact_telegram")} maxLength={100} placeholder="@company_hr" />
          </Field>
          <Field label="Телефон">
            <input className="input" type="tel" value={form.contact_phone} onChange={set("contact_phone")} maxLength={50} placeholder="+7 900 000-00-00" />
          </Field>
        </div>

        <ErrorBox error={saveError} />
        <div>
          <button className="btn btn-primary" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить"}</button>
        </div>
      </form>

      {data.complete && <Verification company={data} onChange={setData} />}
      {data.complete && <AtsIntegration />}
    </div>
  );
}

/** Подтверждение компании: защита кандидатов от фиктивных вакансий и недобросовестных работодателей. */
function Verification({ company, onChange }: { company: EmployerCompany; onChange: (c: EmployerCompany) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function verify() {
    setBusy(true);
    setError(null);
    try {
      const r = await api<EmployerCompany>("/employer/company/verify", { method: "POST" });
      onChange(r);
      toast(r.verification_ok ? "Компания подтверждена" : "Не все проверки пройдены");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className={`card stack ${company.verified ? "" : "card-accent"}`}>
      <div className="row-between">
        <div>
          <h3>Подтверждение компании</h3>
          <p className="small muted" style={{ marginTop: 4 }}>
            Кандидаты видят бейдж «Компания подтверждена» в каждом приглашении. Неподтверждённой компании доступно 5 приглашений в неделю вместо 20.
          </p>
        </div>
        {company.verified
          ? <span className="badge badge-green">✓ Подтверждена {company.verified_at ? dateShort(company.verified_at) : ""}</span>
          : <span className="badge badge-amber">Не подтверждена</span>}
      </div>
      <ul className="reasons">
        {company.verification_checks.map((c) => (
          <li key={c.code} className={c.ok ? "plus" : "minus"}>
            <span className="mark" aria-hidden>{c.ok ? "✓" : "−"}</span>
            <span>{c.text}</span>
          </li>
        ))}
      </ul>
      <p className="tiny muted">
        ИНН проверяется по контрольной сумме ФНС, домен — по совпадению контактного email с сайтом. В продуктиве ИНН сверяется с ЕГРЮЛ,
        а на корпоративный адрес приходит код подтверждения. Изменение ИНН, сайта или email снимает подтверждение.
      </p>
      <ErrorBox error={error} />
      {!company.verified && (
        <div><button className="btn btn-primary" onClick={verify} disabled={busy}>{busy ? "Проверяем…" : "Подтвердить компанию"}</button></div>
      )}
    </div>
  );
}

const EVENT_LABELS: Record<string, string> = {
  "invitation.accepted": "кандидат принял приглашение (с контактами)",
  "invitation.declined": "кандидат отклонил приглашение (причина, ожидания)",
  "application.created": "новый отклик на вакансию (с контактами)",
  "task.submitted": "решение регулярного задания",
  ping: "тестовое событие",
};

/** Интеграция с ATS: исходящие вебхуки с HMAC-подписью и журнал доставок. */
function AtsIntegration() {
  const r = useLoad(() => api<Integrations>("/employer/integrations"));
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  useEffect(() => {
    if (r.data) setUrl(r.data.webhook_url);
  }, [r.data]);

  async function call(path: string, method: string, body?: unknown, ok?: string) {
    setBusy(true);
    setError(null);
    try {
      r.setData(await api<Integrations>(path, { method, body }));
      if (ok) toast(ok);
      if (path.endsWith("/test")) window.setTimeout(() => void r.reload(), 1500);  // доставка идёт в фоне
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (r.loading && !r.data) return <div className="card"><Loading /></div>;
  if (!r.data) return <ErrorBox error={r.error} />;
  const it = r.data;
  return (
    <div className="card stack">
      <div>
        <h3>Интеграция с ATS</h3>
        <p className="small muted" style={{ marginTop: 4 }}>
          Платформа отправляет события в вашу ATS: POST с JSON-телом и подписью <span className="mono">X-FSP-Signature: sha256=HMAC(секрет, тело)</span>.
          До трёх попыток доставки, журнал — ниже. Кандидата с открытыми контактами можно выгрузить в JSON из его карточки.
        </p>
      </div>
      <Field label="URL приёмника" hint="Для проверки можно использовать встроенный демо-приёмник: http://localhost:8000/api/system/webhook-echo">
        <div className="row" style={{ flexWrap: "nowrap" }}>
          <input className="input mono" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://ats.company.ru/hooks/fsp" />
          <button className="btn btn-secondary" disabled={busy || url === it.webhook_url} onClick={() => call("/employer/integrations/webhook", "PUT", { url }, "URL сохранён")}>
            Сохранить
          </button>
        </div>
      </Field>
      {it.webhook_secret && (
        <Field label="Секрет подписи">
          <div className="row" style={{ flexWrap: "nowrap" }}>
            <input className="input mono" readOnly value={showSecret ? it.webhook_secret : "•".repeat(24)} />
            <button className="btn btn-ghost btn-sm" onClick={() => setShowSecret((x) => !x)}>{showSecret ? "Скрыть" : "Показать"}</button>
            <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => call("/employer/integrations/webhook/rotate", "POST", undefined, "Выпущен новый секрет")}>Новый секрет</button>
          </div>
        </Field>
      )}
      <div className="small">
        <div className="strong" style={{ marginBottom: 4 }}>События</div>
        <ul style={{ margin: 0, paddingLeft: 18 }} className="muted">
          {it.events.map((e) => <li key={e}><span className="mono">{e}</span> — {EVENT_LABELS[e] ?? e}</li>)}
        </ul>
      </div>
      <ErrorBox error={error} />
      <div className="row">
        <button className="btn btn-primary" disabled={busy || !it.webhook_url} onClick={() => call("/employer/integrations/webhook/test", "POST", undefined, "Тестовое событие отправлено")}>
          Отправить тестовое событие
        </button>
        <button className="btn btn-ghost" onClick={() => void r.reload()}>Обновить журнал</button>
      </div>
      <div>
        <div className="strong small" style={{ marginBottom: 6 }}>Журнал доставок</div>
        {it.deliveries.length === 0 ? <Empty title="Событий пока не было" /> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Событие</th><th>Статус</th><th>Ответ</th><th>Попыток</th><th>Создано</th></tr></thead>
              <tbody>
                {it.deliveries.map((d) => (
                  <tr key={d.id}>
                    <td className="mono small">{d.event}</td>
                    <td>
                      <span className={`badge ${d.status === "delivered" ? "badge-green" : d.status === "failed" ? "badge-red" : "badge-amber"}`}>
                        {d.status === "delivered" ? "доставлено" : d.status === "failed" ? "ошибка" : "в очереди"}
                      </span>
                    </td>
                    <td className="small">{d.response_code ?? "—"}{d.error ? <div className="tiny muted">{d.error}</div> : null}</td>
                    <td className="small">{d.attempts}</td>
                    <td className="small">{new Date(d.created_at).toLocaleString("ru-RU")}</td>
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
