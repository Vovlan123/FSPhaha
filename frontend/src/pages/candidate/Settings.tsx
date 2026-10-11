import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, downloadFile } from "../../api";
import { ErrorBox, Field, FspBlock, Loading, Switch, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { date } from "../../format";
import type { CandidateProfile, Fsp } from "../../types";

export default function CandidateSettings() {
  const d = useDict();
  const [params, setParams] = useSearchParams();
  const p = useLoad(() => api<CandidateProfile>("/candidate/profile"), []);
  const [form, setForm] = useState<{ show_name: boolean; show_salary: boolean; show_fsp: boolean; show_tasks: boolean; hidden: string; job_status: string; consent_publish: boolean } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fspStatus = params.get("fsp");
  const fspMessage = params.get("message");

  useEffect(() => {
    if (!p.data) return;
    const pr = p.data.privacy;
    setForm({ show_name: pr.show_name, show_salary: pr.show_salary, show_fsp: pr.show_fsp, show_tasks: pr.show_tasks,
      hidden: pr.hidden_companies.join(", "), job_status: p.data.job_status, consent_publish: p.data.consent_publish });
  }, [p.data]);

  if (p.loading && !p.data) return <Loading />;
  if (!p.data || !form) return <ErrorBox error={p.error} />;
  const profile = p.data;

  async function save() {
    if (!form) return;
    setBusy(true);
    setError(null);
    try {
      const r = await api<CandidateProfile>("/candidate/privacy", { method: "PUT", body: {
        show_name: form.show_name, show_salary: form.show_salary, show_fsp: form.show_fsp, show_tasks: form.show_tasks,
        hidden_companies: form.hidden.split(",").map((s) => s.trim()).filter(Boolean), job_status: form.job_status, consent_publish: form.consent_publish,
      } });
      p.setData(r);
      toast("Настройки сохранены");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function fsp(action: "link" | "refresh" | "unlink") {
    setError(null);
    try {
      if (action === "link") {
        const r = await api<{ authorize_url: string }>("/fsp/link/start", { method: "POST" });
        window.location.href = r.authorize_url; // переход на страницу входа ФСП ID (OIDC)
        return;
      }
      const f = await api<Fsp>(action === "refresh" ? "/fsp/refresh" : "/fsp/link", { method: action === "refresh" ? "POST" : "DELETE" });
      p.setData({ ...profile, fsp: f });
      toast(action === "refresh" ? "Достижения обновлены" : "ФСП ID отвязан");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const set = <K extends keyof typeof form>(k: K, v: (typeof form)[K]) => setForm({ ...form, [k]: v });
  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Настройки</h1>
          <p>Что видит работодатель, согласия и связь с ФСП ID.</p>
        </div>
        <button className="btn btn-secondary" onClick={() => downloadFile("/candidate/profile.pdf", "profile.pdf").catch((e) => toast(e.message))}>
          Скачать PDF-профиль
        </button>
      </div>
      {fspStatus && (
        <div className={`alert ${fspStatus === "linked" ? "alert-success" : fspStatus === "cancelled" ? "alert-info" : "alert-error"} row-between`}>
          <span>{fspStatus === "linked" ? "Профиль связан с ФСП ID, достижения загружены." : fspMessage ?? "Не удалось связать ФСП ID"}</span>
          <button className="btn btn-ghost btn-sm" onClick={() => setParams({})}>Скрыть</button>
        </div>
      )}
      <ErrorBox error={error} />
      <div className="sidebar-layout" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)" }}>
        <div className="card stack">
          <h3>Публикация и приватность</h3>
          <Switch
            checked={form.consent_publish}
            onChange={(v) => set("consent_publish", v)}
            label="Согласие на публикацию профиля работодателям"
            hint={profile.consent_publish ? "Профиль участвует в выдаче. Отзыв согласия сразу скрывает его." : "Без согласия работодатели не увидят ваш профиль."}
          />
          <Field label="Статус поиска">
            <select className="select" value={form.job_status} onChange={(e) => set("job_status", e.target.value)}>
              {d.job_statuses.map((j) => <option key={j.code} value={j.code}>{j.label}</option>)}
            </select>
          </Field>
          <div>
            <Switch checked={form.show_name} onChange={(v) => set("show_name", v)} label="Показывать имя до принятия приглашения" hint="По умолчанию работодатель видит псевдоним" />
            <Switch checked={form.show_salary} onChange={(v) => set("show_salary", v)} label="Показывать зарплатные ожидания" />
            <Switch checked={form.show_fsp} onChange={(v) => set("show_fsp", v)} label="Показывать достижения ФСП" hint="Скрытые достижения не учитываются в ранжировании" />
            <Switch checked={form.show_tasks} onChange={(v) => set("show_tasks", v)} label="Показывать результаты регулярных заданий" />
          </div>
          <Field label="Скрыть профиль от компаний" hint="Через запятую, например текущий работодатель">
            <input className="input" value={form.hidden} onChange={(e) => set("hidden", e.target.value)} />
          </Field>
          <div className="small muted">Контакты (email, телефон, Telegram) всегда скрыты, пока вы не примете приглашение или не откликнетесь сами.</div>
          <div className="row"><button className="btn btn-primary" onClick={save} disabled={busy}>Сохранить</button></div>
        </div>
        <div className="stack">
          <div className="card stack">
            <div className="row-between">
              <h3>ФСП ID</h3>
              {profile.fsp.linked ? <span className="badge badge-green">Связан · {profile.fsp.fsp_id}</span> : <span className="badge badge-grey">Не связан</span>}
            </div>
            <p className="small muted">
              Привяжите профиль участника Федерации спортивного программирования — результаты соревнований подтянутся автоматически
              и поднимут вас внутри категории. Если истории ФСП нет, это не штрафуется.
            </p>
            <FspBlock fsp={profile.fsp} />
            {profile.fsp.fetched_at && <div className="tiny muted">Обновлено {date(profile.fsp.fetched_at)}</div>}
            <div className="row">
              {!profile.fsp.linked ? (
                <button className="btn btn-primary" onClick={() => fsp("link")}>Связать с ФСП ID</button>
              ) : (
                <>
                  <button className="btn btn-secondary" onClick={() => fsp("refresh")}>Обновить достижения</button>
                  <button className="btn btn-danger" onClick={() => fsp("unlink")}>Отвязать</button>
                </>
              )}
            </div>
          </div>
          <div className="card stack-sm">
            <h3>Аккаунт и согласия</h3>
            <dl className="kv">
              <dt>Email</dt><dd>{profile.email}</dd>
              <dt>Согласие на обработку ПДн</dt><dd>дано при регистрации</dd>
              <dt>Псевдоним</dt><dd className="mono">{profile.anon_code}</dd>
            </dl>
          </div>
        </div>
      </div>
    </div>
  );
}
