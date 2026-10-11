import { useState, type ReactNode } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api, downloadFile } from "../../api";
import InviteModal from "../../components/InviteModal";
import { ErrorBox, FspBlock, Loading, SkillTags, StatusBadge, StrengthBreakdown, ThetaScale, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { dateShort, pct, rub, years } from "../../format";
import type { CandidateCard, Contacts } from "../../types";
import { CompanyGate, isActiveInvitation } from "./common";

function Section({ title, children, aside }: { title: string; children: ReactNode; aside?: ReactNode }) {
  return (
    <section className="card stack-sm">
      <div className="card-head" style={{ marginBottom: 6 }}>
        <h3>{title}</h3>
        {aside}
      </div>
      {children}
    </section>
  );
}

function ContactsBlock({ c }: { c: Contacts }) {
  const tg = c.telegram?.replace(/^@/, "");
  return (
    <div className="contacts-box stack-sm" style={{ fontSize: 14 }}>
      <div className="strong">Контакты открыты</div>
      <dl className="kv" style={{ gridTemplateColumns: "120px 1fr" }}>
        <dt>ФИО</dt><dd>{c.full_name || "—"}</dd>
        <dt>Email</dt><dd>{c.email ? <a href={`mailto:${c.email}`}>{c.email}</a> : "—"}</dd>
        <dt>Телефон</dt><dd>{c.phone ? <a href={`tel:${c.phone}`}>{c.phone}</a> : "—"}</dd>
        <dt>Telegram</dt><dd>{tg ? <a href={`https://t.me/${tg}`} target="_blank" rel="noreferrer">@{tg}</a> : "—"}</dd>
      </dl>
    </div>
  );
}

function CardView() {
  const { id } = useParams();
  const [params] = useSearchParams();
  const needId = params.get("need") ? Number(params.get("need")) : null;
  const d = useDict();
  const { data: c, error, loading, reload } = useLoad(() => api<CandidateCard>(`/employer/candidates/${id}`), [id]);
  const [inviting, setInviting] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function exportJson() {
    if (!c) return;
    try {
      // Формат для импорта в ATS (person, skills, credentials) — см. документацию, раздел 9.2
      const data = await api<unknown>(`/employer/candidates/${c.id}/export.json`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `candidate-${c.id}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      toast((e as Error).message);
    }
  }

  async function pdf() {
    if (!c) return;
    setDownloading(true);
    try {
      await downloadFile(`/employer/candidates/${c.id}/profile.pdf`, `candidate-${c.anon_code}.pdf`);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setDownloading(false);
    }
  }

  if (loading && !c) return <Loading />;
  if (!c) return <ErrorBox error={error} />;

  const inv = c.last_invitation;
  const canInvite = !isActiveInvitation(inv?.status) && inv?.status !== "accepted";
  const labels = (list: { code: string; label: string }[], codes: string[]) => codes.map((x) => d.label(list, x)).join(", ") || "—";
  const declared = Array.from(new Set([...c.verified_skills, ...c.stack]));

  return (
    <div className="stack-lg">
      <div>
        <Link to={needId ? `/employer/needs/${needId}` : "/employer/bank"} className="small">
          ← {needId ? "К подборке" : "В банк кандидатов"}
        </Link>
      </div>

      <div className="card stack">
        <div className="row-between" style={{ alignItems: "flex-start" }}>
          <div className="stack-sm" style={{ minWidth: 0 }}>
            <div className="row" style={{ gap: 10 }}>
              <h1>{c.display_name}</h1>
              <span className="category">{c.category}</span>
              <span className={`badge ${c.job_status === "active" ? "badge-green" : "badge-blue"}`}>{d.label(d.job_statuses, c.job_status)}</span>
            </div>
            <div className="cand-meta">
              <span>код {c.anon_code}</span>
              <span>{c.city || "город не указан"}{c.relocation ? " · готов к переезду" : ""}</span>
              <span>{c.work_format.length ? labels(d.work_formats, c.work_format) : "формат не указан"}</span>
              <span>опыт {years(c.experience_years)}</span>
            </div>
          </div>
          <div className="stack-sm" style={{ alignItems: "flex-end" }}>
            <span className="tiny muted">Ожидания по зарплате</span>
            {c.salary_expect_min ? <span className="salary salary-lg">от {rub(c.salary_expect_min)}</span> : <span className="muted">скрыты или не указаны</span>}
          </div>
        </div>

        <div className="row">
          {canInvite ? (
            <button className="btn btn-success" onClick={() => setInviting(true)}>{inv ? "Пригласить снова" : "Пригласить"}</button>
          ) : inv ? (
            <span className="small">
              Приглашение: <StatusBadge kind="invitation" status={inv.status} /> <span className="muted">от {dateShort(inv.created_at)}</span>
            </span>
          ) : null}
          <button className="btn btn-secondary" onClick={pdf} disabled={downloading}>
            {downloading ? "Готовим PDF…" : "Скачать PDF-профиль"}
          </button>
          {c.contacts_unlocked && (
            <button className="btn btn-secondary" onClick={exportJson} title="Выгрузка кандидата для импорта в ATS">
              Экспорт в ATS (JSON)
            </button>
          )}
          {inv && canInvite && (
            <span className="small muted">
              Последнее приглашение: <StatusBadge kind="invitation" status={inv.status} /> от {dateShort(inv.created_at)}
            </span>
          )}
        </div>

        {c.contacts_unlocked && c.contacts ? (
          <ContactsBlock c={c.contacts} />
        ) : (
          <div className="alert alert-brand">
            <span aria-hidden>ⓘ</span>
            <span>
              Контакты откроются после того, как кандидат примет приглашение или откликнется сам. До этого профиль анонимен:
              ФИО и контакты скрыты.
            </span>
          </div>
        )}
      </div>

      <div className="grid grid-2">
        <Section title="Уровень по тесту" aside={c.grade_changed_at ? <span className="tiny muted">грейд с {dateShort(c.grade_changed_at)}</span> : null}>
          {c.theta !== null ? (
            <>
              <ThetaScale theta={c.theta} se={c.theta_se} highlight={c.grade} />
              <p className="small muted" style={{ marginTop: 18 }}>
                Оценка уровня θ = {c.theta.toFixed(2)}{c.theta_se ? ` ± ${c.theta_se.toFixed(2)}` : ""}. Положение внутри полосы грейда
                «{d.grade(c.grade)}» — {pct(c.strength.T)}{c.strength.T >= 0.5 ? ": уверенно в грейде" : ""}.
              </p>
            </>
          ) : (
            <p className="muted small">Нет данных теста</p>
          )}
        </Section>
        <Section title="Сила профиля" aside={<span className="salary">{Math.round(c.strength.P * 100)} из 100</span>}>
          <StrengthBreakdown s={c.strength} />
        </Section>
      </div>

      <div className="grid grid-2" style={{ alignItems: "start" }}>
        <Section title="Темы, проверенные тестом">
          {c.verified_topics.length === 0 ? (
            <p className="muted small">Нет данных по темам</p>
          ) : (
            <div className="table-wrap">
              <p className="tiny muted" style={{ marginBottom: 6 }}>
                Вопросы подбираются под уровень кандидата, поэтому результат сравнивается с ожиданием модели для его θ, а не с долей верных.
              </p>
              <table className="table">
                <thead><tr><th>Тема</th><th>Верно</th><th>Ожидалось</th><th>Статус</th></tr></thead>
                <tbody>
                  {c.verified_topics.map((t) => (
                    <tr key={t.topic}>
                      <td>{t.label}</td>
                      <td className="mono small">{t.correct} / {t.total}</td>
                      <td className="mono small muted">{t.expected !== undefined ? t.expected.toFixed(1) : "—"}</td>
                      <td>
                        {t.verified ? <span className="badge badge-green">✓ подтверждено</span>
                          : t.refuted ? <span className="badge badge-amber">слабее остальных</span>
                          : <span className="badge badge-grey">мало данных</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>
        <Section title="Стек">
          <SkillTags skills={declared} verified={c.verified_skills} refuted={c.refuted_skills} />
          <p className="tiny muted">
            <span className="skill verified">✓ навык</span> — заявлен и подтверждён тестом, <span className="skill refuted">⚠ навык</span> — тест не подтвердил, <span className="skill">навык</span> — только заявлен
          </p>
        </Section>
      </div>

      <Section title="О кандидате">
        {c.about && <p style={{ whiteSpace: "pre-wrap" }}>{c.about}</p>}
        <dl className="kv" style={{ marginTop: 8 }}>
          <dt>Опыт</dt><dd>{years(c.experience_years)}</dd>
          <dt>Роли</dt><dd>{labels(d.roles, c.roles)}</dd>
          <dt>Софт-скиллы</dt><dd>{labels(d.soft_skills, c.soft_skills)}</dd>
          <dt>Интересные отрасли</dt><dd>{labels(d.industries, c.industries)}</dd>
        </dl>
      </Section>

      <Section title="Достижения ФСП" aside={c.fsp.visible && c.fsp.achievements.length > 0 ? <span className="tiny muted">подтверждены реестром ФСП</span> : null}>
        <FspBlock fsp={c.fsp} />
      </Section>

      <Section title="Регулярные задания">
        {c.tasks.length === 0 ? (
          <p className="muted small">Решённых заданий нет или кандидат скрыл результаты.</p>
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Задание</th><th>Тип</th><th>Автооценка</th><th>Оценка работодателя</th><th>Дата</th></tr></thead>
              <tbody>
                {c.tasks.map((t, i) => (
                  <tr key={i}>
                    <td>{t.title}</td>
                    <td className="small">{t.kind === "solve" ? "Решить" : "Предложить подход"}</td>
                    <td>{pct(t.auto_score)}</td>
                    <td>{t.employer_score ? `${t.employer_score} из 5` : "—"}</td>
                    <td className="small">{dateShort(t.submitted_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      {inviting && (
        <InviteModal
          candidate={{ id: c.id, display_name: c.display_name, category: c.category, salary_expect_min: c.salary_expect_min }}
          needId={needId}
          onClose={() => setInviting(false)}
          onSent={() => void reload()}
        />
      )}
    </div>
  );
}

export default function CandidateCardPage() {
  return (
    <CompanyGate>
      <CardView />
    </CompanyGate>
  );
}
