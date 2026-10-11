import { Link, Navigate } from "react-router-dom";
import { api, downloadFile } from "../../api";
import { ErrorBox, FspBlock, Loading, StrengthBreakdown, ThetaScale, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { date } from "../../format";
import type { CandidateStatus } from "../../types";

export default function CandidateDashboard() {
  const d = useDict();
  const st = useLoad(() => api<CandidateStatus>("/candidate/status"), []);
  if (st.loading && !st.data) return <Loading />;
  if (st.error || !st.data) return <ErrorBox error={st.error} />;
  const s = st.data;
  if (!s.onboarding_complete && !s.grade) return <Navigate to="/candidate/onboarding" replace />;

  return (
    <div className="stack-lg">
      <div className="card hero-card">
        <div className="row-between" style={{ alignItems: "flex-start" }}>
          <div className="stack-sm">
            <span className="small muted">Ваша категория</span>
            <h1>{s.category}</h1>
            <span className="small muted">
              Грейд подтверждён {date(s.grade_changed_at)} · следующая смена грейда — не раньше {date(s.next_grade_change_at)}
            </span>
          </div>
          <div className="stack-sm" style={{ alignItems: "flex-end" }}>
            <span className="small muted">Сила профиля</span>
            <span style={{ fontSize: 40, fontWeight: 800, lineHeight: 1 }}>{Math.round(s.strength.P * 100)}</span>
            <span className="tiny muted">из 100 — по ней вы ранжируетесь в категории</span>
          </div>
        </div>
      </div>

      {!s.visible_to_employers && (
        <div className="alert alert-warn row-between">
          <span>
            {s.job_status === "closed"
              ? "Статус «Не ищу работу» — профиль скрыт из выдачи."
              : "Профиль не виден работодателям: нет согласия на публикацию."}
          </span>
          <Link to="/candidate/settings" className="btn btn-primary btn-sm">Открыть настройки</Link>
        </div>
      )}
      {s.new_invitations > 0 && (
        <div className="alert alert-success row-between">
          <span>Новых приглашений: <b>{s.new_invitations}</b>. Вилка зарплаты указана в каждом.</span>
          <Link to="/candidate/invitations" className="btn btn-success btn-sm">Посмотреть</Link>
        </div>
      )}
      {s.active_attempt_id && (
        <div className="alert alert-warn row-between">
          <span>Есть незавершённый тест.</span>
          <Link to={`/candidate/test/${s.active_attempt_id}`} className="btn btn-primary btn-sm">Продолжить</Link>
        </div>
      )}

      <div className="grid grid-3">
        <div className="card stack">
          <h3>Из чего складывается сила профиля</h3>
          <StrengthBreakdown s={s.strength} />
        </div>
        <div className="card stack">
          <div className="row-between">
            <h3>Уровень по тесту</h3>
            <Link to="/candidate/grade" className="small">История</Link>
          </div>
          {s.theta !== null && <ThetaScale theta={s.theta} se={s.theta_se} highlight={s.grade} />}
          <div className="small">
            <span className="strong">Подтверждено тестом: </span>
            {s.verified_skills.length ? s.verified_skills.map((v) => d.skill(v.code)).join(", ") : "—"}
          </div>
        </div>
        <div className="card stack">
          <div className="row-between">
            <h3>Достижения ФСП</h3>
            <Link to="/candidate/settings" className="small">{s.fsp.linked ? "Управлять" : "Связать"}</Link>
          </div>
          <FspBlock fsp={s.fsp} compact />
          {!s.fsp.linked && <Link to="/candidate/settings" className="btn btn-secondary btn-sm">Связать с ФСП ID</Link>}
        </div>
      </div>

      <div className="grid grid-4">
        <Link to="/candidate/invitations" className="card card-link">
          <h4>Приглашения</h4>
          <p className="small muted">Предложения от работодателей с вилкой зарплаты</p>
        </Link>
        <Link to="/candidate/tasks" className="card card-link">
          <h4>Регулярные задания</h4>
          <p className="small muted">{s.next_task_at ? `Следующее — с ${date(s.next_task_at)}` : "Короткая задача от работодателя ждёт вас"}</p>
        </Link>
        <Link to="/candidate/vacancies" className="card card-link">
          <h4>Вакансии</h4>
          <p className="small muted">Откликнитесь сами, если приглашений пока нет</p>
        </Link>
        <button
          className="card card-link"
          style={{ textAlign: "left" }}
          onClick={() => downloadFile("/candidate/profile.pdf", "profile.pdf").catch((e) => toast(e.message))}
        >
          <h4>PDF-профиль</h4>
          <p className="small muted">Стандартизированный профиль для отправки</p>
        </button>
      </div>
    </div>
  );
}
