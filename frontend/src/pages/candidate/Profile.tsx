import { useState } from "react";
import { api } from "../../api";
import { ErrorBox, Loading, Tabs, toast, useLoad } from "../../components/ui";
import type { CandidateProfile } from "../../types";
import { ProfileForm, SurveyForm } from "./forms";

export default function CandidateProfilePage() {
  const p = useLoad(() => api<CandidateProfile>("/candidate/profile"), []);
  const [tab, setTab] = useState<"profile" | "survey">("profile");
  if (p.loading && !p.data) return <Loading />;
  if (!p.data) return <ErrorBox error={p.error} />;
  const saved = (np: CandidateProfile) => {
    p.setData(np);
    toast("Сохранено");
  };
  return (
    <div className="stack-lg">
      <div className="page-head">
        <div>
          <h1>Профиль и опрос</h1>
          <p>Личные данные видны работодателю только после принятия приглашения. Изменения стека учитываются в следующем тесте.</p>
        </div>
      </div>
      <Tabs value={tab} onChange={setTab} tabs={[{ key: "profile", label: "Профиль" }, { key: "survey", label: "Опрос" }]} />
      <div className="card">
        {tab === "profile" ? (
          <ProfileForm key="profile" profile={p.data} onSaved={saved} submitLabel="Сохранить" />
        ) : (
          <SurveyForm key="survey" profile={p.data} onSaved={saved} submitLabel="Сохранить опрос" />
        )}
      </div>
    </div>
  );
}
