import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api";
import { useAuth } from "../auth";
import { Field } from "../components/ui";
import type { Role, User } from "../types";

function AuthCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="card stack auth-card">
      <div>
        <h2>{title}</h2>
        {subtitle && <p className="muted small" style={{ marginTop: 6 }}>{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

function PasswordField({ value, onChange, autoComplete, hint }: { value: string; onChange: (v: string) => void; autoComplete: string; hint?: string }) {
  const [show, setShow] = useState(false);
  return (
    <Field label="Пароль" hint={hint}>
      <div className="input-wrap">
        <input
          className="input"
          type={show ? "text" : "password"}
          autoComplete={autoComplete}
          required
          minLength={autoComplete === "new-password" ? 8 : undefined}
          value={value}
          onChange={(e) => onChange(e.target.value)}
        />
        <button type="button" className="input-action" onClick={() => setShow((s) => !s)} aria-pressed={show}>
          {show ? "Скрыть" : "Показать"}
        </button>
      </div>
    </Field>
  );
}

function DevLink({ link }: { link: string }) {
  // В демо-режиме бэкенд возвращает ссылку из письма, чтобы проверяющему не нужен был почтовый ящик
  const path = link.replace(/^https?:\/\/[^/]+/, "");
  return (
    <div className="alert alert-info">
      <span aria-hidden>✉</span>
      <span>
        Демо-режим: письмо записано в лог сервера. <Link to={path} className="strong">Открыть ссылку подтверждения</Link>
      </span>
    </div>
  );
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [needVerify, setNeedVerify] = useState(false);
  const [devLink, setDevLink] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const u = await login(email, password);
      nav(params.get("next") || (u.role === "candidate" ? "/candidate" : "/employer"), { replace: true });
    } catch (err) {
      const ae = err as ApiError;
      setError(ae.message);
      setNeedVerify(ae.status === 403);
    } finally {
      setBusy(false);
    }
  }

  async function resend() {
    try {
      const r = await api<{ message: string; dev_verify_link: string | null }>("/auth/resend", { body: { email, password } });
      setError(r.message);
      setDevLink(r.dev_verify_link);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <AuthCard title="Вход" subtitle="Демо-аккаунты можно подставить одним нажатием — пароль demo12345">
      <div className="demo-accounts">
        <span className="tiny muted">Быстрый вход:</span>
        <button type="button" className="chip" onClick={() => { setEmail("candidate@demo.ru"); setPassword("demo12345"); }}>Кандидат</button>
        <button type="button" className="chip" onClick={() => { setEmail("employer@demo.ru"); setPassword("demo12345"); }}>Работодатель</button>
      </div>
      <form className="stack" onSubmit={submit}>
        <Field label="Email">
          <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <PasswordField value={password} onChange={setPassword} autoComplete="current-password" />
        {error && <div className={`alert ${needVerify ? "alert-warn" : "alert-error"}`} role="alert">{error}</div>}
        {needVerify && !devLink && <button type="button" className="btn btn-secondary" onClick={resend}>Отправить письмо ещё раз</button>}
        {devLink && <DevLink link={devLink} />}
        <button className="btn btn-primary btn-block" disabled={busy}>{busy ? "Входим…" : "Войти"}</button>
      </form>
      <p className="small muted">Нет аккаунта? <Link to="/register">Зарегистрироваться</Link></p>
    </AuthCard>
  );
}

export function Register() {
  const [params] = useSearchParams();
  const [role, setRole] = useState<Role>(params.get("role") === "employer" ? "employer" : "candidate");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [consent, setConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ message: string; link: string | null } | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<{ message: string; dev_verify_link: string | null }>("/auth/register", {
        body: { email, password, role, consent_pd: consent },
      });
      setDone({ message: r.message, link: r.dev_verify_link });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (done)
    return (
      <AuthCard title="Подтвердите email" subtitle={done.message}>
        <p className="small">Перейдите по ссылке из письма, отправленного на <b>{email}</b>. После подтверждения вы попадёте в кабинет.</p>
        {done.link && <DevLink link={done.link} />}
      </AuthCard>
    );

  return (
    <AuthCard title="Регистрация">
      <div className="grid grid-2" role="radiogroup" aria-label="Роль">
        {([["candidate", "Я ищу работу", "Пройду тест и получу приглашения"], ["employer", "Я ищу специалистов", "Найду кандидатов по категориям"]] as const).map(([r, t, s]) => (
          <button
            key={r}
            type="button"
            role="radio"
            aria-checked={role === r}
            className={`card card-tight card-link ${role === r ? "card-accent" : ""}`}
            style={{ textAlign: "left", borderColor: role === r ? "var(--brand-500)" : undefined }}
            onClick={() => setRole(r)}
          >
            <div className="strong">{t}</div>
            <div className="tiny muted">{s}</div>
          </button>
        ))}
      </div>
      <form className="stack" onSubmit={submit}>
        <Field label="Email">
          <input className="input" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <PasswordField value={password} onChange={setPassword} autoComplete="new-password" hint="Не короче 8 символов" />
        <label className="check">
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          <span className="small">
            Даю согласие на обработку персональных данных в соответствии с Федеральным законом № 152-ФЗ
            «О персональных данных» для целей подбора персонала. Публикация профиля работодателям — отдельным согласием в настройках.
          </span>
        </label>
        {error && <div className="alert alert-error" role="alert">{error}</div>}
        <button className="btn btn-primary btn-block" disabled={!consent || busy}>{busy ? "Регистрируем…" : "Зарегистрироваться"}</button>
      </form>
      <p className="small muted">Уже есть аккаунт? <Link to="/login">Войти</Link></p>
    </AuthCard>
  );
}

export function Verify() {
  const [params] = useSearchParams();
  const { setSession } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return; // StrictMode вызывает эффект дважды, а токен одноразовый
    started.current = true;
    const token = params.get("token");
    if (!token) {
      setError("В ссылке нет токена подтверждения");
      return;
    }
    api<{ access_token: string; user: User }>(`/auth/verify?token=${encodeURIComponent(token)}`)
      .then((r) => {
        setSession(r.access_token, r.user);
        nav(r.user.role === "candidate" ? "/candidate/onboarding" : "/employer/company", { replace: true });
      })
      .catch((e) => setError(e.message));
  }, [params, setSession, nav]);

  return (
    <AuthCard title="Подтверждение email">
      {error ? (
        <>
          <div className="alert alert-error">{error}</div>
          <Link to="/login" className="btn btn-secondary">Ко входу</Link>
        </>
      ) : (
        <div className="row"><div className="spinner" /> <span>Подтверждаем адрес…</span></div>
      )}
    </AuthCard>
  );
}
