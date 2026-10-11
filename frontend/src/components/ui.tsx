import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useDict } from "../dict";
import { salaryRange } from "../format";
import type { Fsp, Reason, Strength } from "../types";

// ---------- загрузка данных

export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setData(await fnRef.current());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => {
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading, reload, setData };
}

export function Loading() {
  return (
    <div className="loading" role="status" aria-label="Загрузка">
      <div className="spinner" />
    </div>
  );
}

export function ErrorBox({ error }: { error: string | null }) {
  if (!error) return null;
  return <div className="alert alert-error" role="alert">{error}</div>;
}

export function Empty({ icon = "○", title, children }: { icon?: string; title: string; children?: ReactNode }) {
  return (
    <div className="empty">
      <div className="icon" aria-hidden>{icon}</div>
      <h3>{title}</h3>
      {children && <div className="small">{children}</div>}
    </div>
  );
}

// ---------- уведомления

export function toast(message: string) {
  window.dispatchEvent(new CustomEvent("toast", { detail: message }));
}

export function Toaster() {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    let t: number | undefined;
    const on = (e: Event) => {
      setMsg((e as CustomEvent<string>).detail);
      window.clearTimeout(t);
      t = window.setTimeout(() => setMsg(null), 3200);
    };
    window.addEventListener("toast", on);
    return () => window.removeEventListener("toast", on);
  }, []);
  return msg ? <div className="toast" role="status">{msg}</div> : null;
}

// ---------- модальное окно

export function Modal({ title, onClose, children, footer, wide }: { title: ReactNode; onClose: () => void; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-back" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="modal" role="dialog" aria-modal="true" style={wide ? { width: "min(860px, 100%)" } : undefined}>
        <div className="modal-head">
          <h3>{title}</h3>
          <button className="close-x" onClick={onClose} aria-label="Закрыть">×</button>
        </div>
        <div className="modal-body">{children}</div>
        {footer && <div className="modal-foot">{footer}</div>}
      </div>
    </div>
  );
}

// ---------- формы

export function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string | null; children: ReactNode }) {
  return (
    <div className="field">
      <label>{label}</label>
      {children}
      {error ? <span className="error">{error}</span> : hint ? <span className="hint">{hint}</span> : null}
    </div>
  );
}

export function ChipSelect({ options, value, onChange, max }: { options: { code: string; label: string }[]; value: string[]; onChange: (v: string[]) => void; max?: number }) {
  return (
    <div className="chips" role="group">
      {options.map((o) => {
        const on = value.includes(o.code);
        return (
          <button
            type="button"
            key={o.code}
            className={`chip ${on ? "on" : ""}`}
            aria-pressed={on}
            onClick={() => {
              if (on) onChange(value.filter((x) => x !== o.code));
              else if (!max || value.length < max) onChange([...value, o.code]);
            }}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}

export function Switch({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; hint?: ReactNode }) {
  return (
    <label className="switch-row">
      <div>
        <div className="strong">{label}</div>
        {hint && <div className="small muted">{hint}</div>}
      </div>
      <span className="switch">
        <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
        <span />
      </span>
    </label>
  );
}

// ---------- отображение

const STATUS_COLORS: Record<string, string> = {
  sent: "badge-blue", viewed: "badge-amber", accepted: "badge-green", declined: "badge-red", withdrawn: "badge-grey",
  expired: "badge-grey", invited: "badge-green", rejected: "badge-red", published: "badge-green", closed: "badge-grey",
  assigned: "badge-amber", submitted: "badge-green", skipped: "badge-grey", confirmed: "badge-green",
  confirmed_plus: "badge-green", not_confirmed: "badge-red", in_progress: "badge-amber", finished: "badge-green", abandoned: "badge-grey",
};

export function StatusBadge({ kind, status, label }: { kind: string; status: string; label?: string }) {
  const d = useDict();
  return <span className={`badge ${STATUS_COLORS[status] ?? ""}`}>{label ?? d.status(kind, status)}</span>;
}

export function Salary({ from, to, large }: { from: number; to: number; large?: boolean }) {
  return <span className={`salary ${large ? "salary-lg" : ""}`}>{salaryRange(from, to)}</span>;
}

export function ReasonList({ reasons, limit }: { reasons: Reason[]; limit?: number }) {
  const list = limit ? reasons.slice(0, limit) : reasons;
  return (
    <ul className="reasons">
      {list.map((r, i) => (
        <li key={i} className={r.kind}>
          <span className="mark" aria-hidden>{r.kind === "plus" ? "+" : r.kind === "minus" ? "−" : "•"}</span>
          <span>{r.text}</span>
        </li>
      ))}
    </ul>
  );
}

export function ScoreRing({ value, title }: { value: number; title?: string }) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  return (
    <div className="score" style={{ ["--p" as string]: v }} title={title ?? `Соответствие ${v} из 100`} aria-label={`Соответствие ${v} из 100`}>
      <span>{v}</span>
    </div>
  );
}

export function Bar({ value, green }: { value: number; green?: boolean }) {
  return (
    <div className={`bar ${green ? "green" : ""}`} aria-hidden>
      <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />
    </div>
  );
}

export function StrengthBreakdown({ s }: { s: Strength }) {
  const rows: [string, number, string][] = [
    ["Тест", s.T, "положение уровня внутри полосы грейда · вес 60%"],
    ["ФСП", s.F, "достижения в реестре ФСП с учётом давности · вес 25%"],
    ["Активность", s.A, "регулярные задания за последние месяцы · вес 15%"],
  ];
  return (
    <div className="stack-sm">
      {rows.map(([label, v, hint]) => (
        <div key={label}>
          <div className="row-between small">
            <span className="strong">{label}</span>
            <span className="muted">{Math.round(v * 100)}%</span>
          </div>
          <Bar value={v} />
          <div className="tiny muted">{hint}</div>
        </div>
      ))}
    </div>
  );
}

export function SkillTags({ skills, verified = [], refuted = [], missing = [] }: { skills: string[]; verified?: string[]; refuted?: string[]; missing?: string[] }) {
  const d = useDict();
  return (
    <div className="chips">
      {skills.map((s) => {
        const kind = verified.includes(s) ? "verified" : refuted.includes(s) ? "refuted" : "";
        const title = kind === "verified" ? "Заявлено и подтверждено тестом" : kind === "refuted" ? "Заявлено, но тест не подтвердил" : "Заявлено кандидатом";
        return (
          <span key={s} className={`skill ${kind}`} title={title}>
            {kind === "verified" && <span aria-hidden>✓</span>}
            {kind === "refuted" && <span aria-hidden>⚠</span>}
            {d.skill(s)}
          </span>
        );
      })}
      {missing.map((s) => (
        <span key={s} className="skill miss" title="Нет в профиле">{d.skill(s)}</span>
      ))}
    </div>
  );
}

export function CodeBlock({ code, lang }: { code: string; lang?: string | null }) {
  return (
    <div>
      {lang && <div className="code-lang">{lang}</div>}
      <pre className="code">{code}</pre>
    </div>
  );
}

export function ThetaScale({ theta, se, highlight }: { theta: number; se?: number | null; highlight?: string | null }) {
  const d = useDict();
  const min = -2.5;
  const max = 3;
  const pos = (x: number) => `${((Math.max(min, Math.min(max, x)) - min) / (max - min)) * 100}%`;
  return (
    <div className="scale" aria-label={`Оценка уровня ${theta.toFixed(2)}`}>
      <div className="track" />
      {se ? <div className="band" style={{ left: pos(theta - se), width: `calc(${pos(theta + se)} - ${pos(theta - se)})` }} /> : null}
      {d.grades.map((g) => (
        <div key={g.code} className="cut" style={{ left: pos(g.cutoff), background: highlight === g.code ? "var(--green)" : undefined }}>
          <span>{g.label}</span>
        </div>
      ))}
      <div className="marker" style={{ left: pos(theta) }} />
      <div className="marker-label" style={{ left: pos(theta) }}>θ = {theta.toFixed(2)}</div>
    </div>
  );
}

export function FspBlock({ fsp, compact }: { fsp: Fsp; compact?: boolean }) {
  if (!fsp.linked || !fsp.visible || fsp.achievements.length === 0) {
    return (
      <div className="alert alert-brand">
        <span aria-hidden>ⓘ</span>
        <span>{fsp.status_text ?? "Нет данных ФСП"}</span>
      </div>
    );
  }
  const list = compact ? fsp.achievements.slice(0, 3) : fsp.achievements;
  return (
    <div className="stack-sm">
      {list.map((a) => (
        <div key={a.event_id} className="row" style={{ alignItems: "flex-start", gap: 10 }}>
          <span className={`badge ${a.result === "winner" ? "badge-solid" : a.result === "prize" ? "" : "badge-grey"}`} style={{ minWidth: 92, justifyContent: "center" }}>
            {a.result_label}{a.place ? ` · ${a.place} место` : ""}
          </span>
          <div>
            <div className="strong small">{a.event_name}</div>
            <div className="tiny muted">
              {a.level_label} уровень · {a.discipline_label} · {a.date?.slice(0, 4)}
              {a.team_name ? ` · команда «${a.team_name}»${a.team_role === "captain" ? ", капитан" : ""}` : ""}
            </div>
          </div>
        </div>
      ))}
      {compact && fsp.achievements.length > 3 && <div className="tiny muted">и ещё {fsp.achievements.length - 3}</div>}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { key: T; label: string; count?: number }[]; value: T; onChange: (v: T) => void }) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.key} role="tab" aria-selected={t.key === value} className={`tab ${t.key === value ? "active" : ""}`} onClick={() => onChange(t.key)}>
          {t.label}
          {t.count !== undefined && <span className="count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}
