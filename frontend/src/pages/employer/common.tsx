// Общие элементы кабинета работодателя: проверка профиля компании, компактные блоки кандидата.
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api, getToken } from "../../api";
import BlueprintView from "../../components/BlueprintView";
import { Bar, ErrorBox, Loading, Modal, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { rub, years } from "../../format";
import type { Blueprint, CandidateSummary, EmployerCompany, Strength } from "../../types";

// Название компании нельзя стереть (сервер требует name), поэтому достаточно запомнить факт заполнения
// для текущего токена и не перезапрашивать его на каждой странице.
let completeForToken: string | null = null;

export function markCompanyComplete() {
  completeForToken = getToken();
}

export function CompanyCta() {
  return (
    <div className="card card-accent stack" style={{ maxWidth: 720 }}>
      <h2>Сначала заполните профиль компании</h2>
      <p className="muted">
        Кандидаты видят, кто их приглашает. Пока у компании нет названия, подбор, банк кандидатов и приглашения
        недоступны.
      </p>
      <div>
        <Link to="/employer/company" className="btn btn-primary">Заполнить профиль компании</Link>
      </div>
    </div>
  );
}

/** Показывает страницу только когда профиль компании заполнен, иначе — CTA. */
export function CompanyGate({ children }: { children: ReactNode }) {
  const token = getToken();
  const [state, setState] = useState<"loading" | "ok" | "incomplete" | "error">(
    completeForToken && completeForToken === token ? "ok" : "loading",
  );
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (state !== "loading") return;
    api<EmployerCompany>("/employer/company")
      .then((c) => {
        if (c.complete) {
          markCompanyComplete();
          setState("ok");
        } else setState("incomplete");
      })
      .catch((e: Error) => {
        setError(e.message);
        setState("error");
      });
  }, [state]);
  if (state === "loading") return <Loading />;
  if (state === "error") return <ErrorBox error={error} />;
  if (state === "incomplete") return <CompanyCta />;
  return <>{children}</>;
}

export const isActiveInvitation = (status?: string | null) => status === "sent" || status === "viewed";

export function CandidateMeta({ c }: { c: CandidateSummary }) {
  const d = useDict();
  return (
    <div className="cand-meta">
      <span>{c.city || "город не указан"}{c.relocation ? " · готов к переезду" : ""}</span>
      <span>{c.work_format?.length ? c.work_format.map((f) => d.label(d.work_formats, f)).join(", ") : "формат не указан"}</span>
      <span>опыт {years(c.experience_years)}</span>
      <span>
        ожидания:{" "}
        <b className="nowrap" style={{ color: "var(--ink)" }}>
          {c.salary_expect_min ? `от ${rub(c.salary_expect_min)}` : "скрыты или не указаны"}
        </b>
      </span>
    </div>
  );
}

/** Три коротких полоски силы профиля: тест, ФСП, активность. */
export function MiniStrength({ s }: { s: Strength }) {
  const rows: [string, number][] = [["Тест", s.T], ["ФСП", s.F], ["Активность", s.A]];
  return (
    <div className="mini-strength" title={`Сила профиля ${Math.round(s.P * 100)} из 100`}>
      {rows.map(([label, v]) => (
        <div key={label}>
          <div className="lbl"><span>{label}</span><span>{Math.round(v * 100)}%</span></div>
          <Bar value={v} />
        </div>
      ))}
    </div>
  );
}

const SCORE_PARTS: [string, string, number][] = [
  ["S", "Стек", 35],
  ["P", "Сила профиля", 30],
  ["G", "Грейд", 15],
  ["C", "Условия: зарплата, формат, город", 20],
];

/** Разложение балла соответствия на факторы (формула из «Механики подбора»). */
export function ScoreParts({ components }: { components: Record<string, number> }) {
  return (
    <div className="stack-sm" style={{ maxWidth: 460 }}>
      {SCORE_PARTS.map(([k, label, w]) => (
        <div key={k}>
          <div className="row-between tiny">
            <span>{label} <span className="muted">· вес {w}%</span></span>
            <span className="strong">{Math.round((components[k] ?? 0) * 100)}%</span>
          </div>
          <Bar value={components[k] ?? 0} />
        </div>
      ))}
    </div>
  );
}

/** «Какие задания получит кандидат»: план теста под потребность или вакансию. */
export function BlueprintModal({ path, title, onClose }: { path: string; title: string; onClose: () => void }) {
  const { data, error, loading } = useLoad(() => api<Blueprint>(path), [path]);
  return (
    <Modal title={title} onClose={onClose} wide>
      {loading && <Loading />}
      <ErrorBox error={error} />
      {data && <BlueprintView bp={data} />}
    </Modal>
  );
}
