import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api";
import { ErrorBox, Loading, useLoad } from "../../components/ui";
import type { CandidateProfile, CandidateStatus } from "../../types";
import { GradePicker, ProfileForm, SurveyForm, type ResumeHints } from "./forms";

const STEPS = ["Профиль", "Опрос", "Грейд и тест", "Категория"];

export default function Onboarding() {
  const data = useLoad(async () => {
    const [profile, status] = await Promise.all([api<CandidateProfile>("/candidate/profile"), api<CandidateStatus>("/candidate/status")]);
    return { profile, status };
  }, []);
  const [step, setStep] = useState(0);
  const [hints, setHints] = useState<ResumeHints | null>(null);

  useEffect(() => {
    if (!data.data) return;
    const s = data.data.status.steps;
    setStep(!s.profile ? 0 : !s.survey ? 1 : !s.test ? 2 : 3);
  }, [data.data]);

  if (data.loading && !data.data) return <Loading />;
  if (data.error || !data.data) return <ErrorBox error={data.error} />;
  const { profile, status } = data.data;
  const done = [status.steps.profile, status.steps.survey, status.steps.test, status.steps.test];

  const setProfile = (p: CandidateProfile) => data.setData({ profile: p, status: data.data!.status });
  const afterSave = async (p: CandidateProfile, next: number) => {
    setProfile(p);
    const st = await api<CandidateStatus>("/candidate/status");
    data.setData({ profile: p, status: st });
    setStep(next);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Путь кандидата</h1>
          <p>Категорию, которую видит работодатель, определяет не резюме, а опрос и адаптивный тест. Это займёт около 20 минут.</p>
        </div>
      </div>
      <div className="steps" aria-label="Шаги">
        {STEPS.map((t, i) => (
          <button
            key={t}
            type="button"
            className={`step ${i === step ? "active" : done[i] ? "done" : ""}`}
            onClick={() => (i <= 2 && (i === 0 || done[i - 1]) ? setStep(i) : undefined)}
            aria-current={i === step ? "step" : undefined}
          >
            <span className="num">{done[i] && i !== step ? "✓" : i + 1}</span>
            {t}
          </button>
        ))}
      </div>

      {status.active_attempt_id && (
        <div className="alert alert-warn row-between">
          <span>У вас есть незавершённый тест.</span>
          <Link className="btn btn-primary btn-sm" to={`/candidate/test/${status.active_attempt_id}`}>Продолжить тест</Link>
        </div>
      )}

      <div className="card">
        {step === 0 && (
          <>
            <h2 style={{ marginBottom: 16 }}>Профиль</h2>
            <ProfileForm profile={profile} onHints={setHints} onSaved={(p) => afterSave(p, 1)} />
          </>
        )}
        {step === 1 && (
          <>
            <h2 style={{ marginBottom: 16 }}>Опрос: отрасль и специализация</h2>
            <SurveyForm profile={profile} hints={hints} onSaved={(p) => afterSave(p, 2)} />
          </>
        )}
        {step === 2 && (
          <>
            <h2 style={{ marginBottom: 6 }}>Какой у вас грейд?</h2>
            <p className="muted small" style={{ marginBottom: 16 }}>Выберите уровень, на который хотите подтвердиться. Тест проверит именно его.</p>
            <GradePicker currentGrade={status.grade} suggested={hints?.grade_guess ?? null} />
          </>
        )}
        {step === 3 && (
          <div className="stack">
            <div className="row">
              <span className="category" style={{ fontSize: 16 }}>{status.category}</span>
              <span className="badge badge-green">Категория присвоена</span>
            </div>
            <h2>Готово! Теперь работодатели могут найти вас сами</h2>
            <p className="muted">Осталось два шага, чтобы профиль работал в полную силу:</p>
            <div className="grid grid-2">
              <div className={`card card-tight ${status.steps.publish ? "" : "card-accent"}`}>
                <div className="strong">{status.steps.publish ? "✓ Профиль опубликован" : "Опубликовать профиль"}</div>
                <div className="small muted">Без согласия на публикацию работодатели вас не увидят.</div>
                {!status.steps.publish && <Link to="/candidate/settings" className="btn btn-primary btn-sm" style={{ marginTop: 8 }}>Дать согласие</Link>}
              </div>
              <div className={`card card-tight ${status.steps.fsp ? "" : "card-accent"}`}>
                <div className="strong">{status.steps.fsp ? "✓ ФСП ID привязан" : "Привязать ФСП ID"}</div>
                <div className="small muted">Достижения в соревнованиях поднимут вас внутри категории.</div>
                {!status.steps.fsp && <Link to="/candidate/settings" className="btn btn-secondary btn-sm" style={{ marginTop: 8 }}>Связать с ФСП ID</Link>}
              </div>
            </div>
            <div className="row"><Link to="/candidate" className="btn btn-primary">В личный кабинет</Link></div>
          </div>
        )}
      </div>
    </div>
  );
}
