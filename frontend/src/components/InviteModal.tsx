// Форма приглашения кандидата: обязательная вилка, предупреждение о вилке ниже ожиданий, недельная квота.
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { useDict } from "../dict";
import { rub } from "../format";
import type { CandidateCard, EmployerCompany, Invitation, Need, Quota, Vacancy } from "../types";
import SalaryFields, { parseRub, salaryError } from "./SalaryFields";
import { ChipSelect, ErrorBox, Field, Loading, Modal, toast } from "./ui";

export type InviteTarget = {
  id: number;
  display_name: string;
  category?: string | null;
  /** undefined — ожидания неизвестны, модалка подгрузит их из карточки кандидата */
  salary_expect_min?: number | null;
};

type Refs = { quota: Quota; company: EmployerCompany; needs: Need[]; vacancies: Vacancy[] };

type Prefill = { title: string; description: string; salary_from: number; salary_to: number; work_format: string[] };

function fromNeed(n: Need): Prefill {
  const description = [n.description, n.team_about ? `Команда: ${n.team_about}` : ""].filter(Boolean).join("\n\n");
  return { title: n.title, description, salary_from: n.salary_from, salary_to: n.salary_to, work_format: n.work_format };
}

function fromVacancy(v: Vacancy): Prefill {
  return { title: v.title, description: v.description, salary_from: v.salary_from, salary_to: v.salary_to, work_format: v.work_format };
}

function contactFromCompany(c: EmployerCompany): string {
  const parts = [c.contact_telegram && `Telegram ${c.contact_telegram}`, c.contact_email, c.contact_phone].filter(Boolean);
  return parts.join(" или ");
}

export default function InviteModal({
  candidate,
  needId,
  vacancyId,
  onClose,
  onSent,
}: {
  candidate: InviteTarget;
  needId?: number | null;
  vacancyId?: number | null;
  onClose: () => void;
  onSent?: (inv: Invitation) => void;
}) {
  const d = useDict();
  const [refs, setRefs] = useState<Refs | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [expect, setExpect] = useState<number | null>(candidate.salary_expect_min ?? null);

  const [link, setLink] = useState(needId ? `need:${needId}` : vacancyId ? `vacancy:${vacancyId}` : "");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [salaryFrom, setSalaryFrom] = useState("");
  const [salaryTo, setSalaryTo] = useState("");
  const [formats, setFormats] = useState<string[]>([]);
  const [contact, setContact] = useState("");
  const [tried, setTried] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const prefilled = useRef(false);

  function apply(p: Prefill) {
    setTitle(p.title.slice(0, 200));
    setDescription(p.description.slice(0, 6000));
    setSalaryFrom(String(p.salary_from));
    setSalaryTo(String(p.salary_to));
    setFormats(p.work_format);
  }

  useEffect(() => {
    Promise.all([
      api<Quota>("/employer/invitations/quota"),
      api<EmployerCompany>("/employer/company"),
      api<Need[]>("/employer/needs"),
      api<Vacancy[]>("/employer/vacancies"),
    ])
      .then(([quota, company, needs, vacancies]) => setRefs({ quota, company, needs, vacancies }))
      .catch((e: Error) => setLoadError(e.message));
    if (candidate.salary_expect_min === undefined) {
      // Из заданий и откликов ожидания не приходят — берём их из карточки (null, если кандидат их скрыл)
      api<CandidateCard>(`/employer/candidates/${candidate.id}`)
        .then((c) => setExpect(c.salary_expect_min))
        .catch(() => undefined);
    }
  }, [candidate.id, candidate.salary_expect_min]);

  // Первичное заполнение: контакты компании и данные потребности/вакансии, из которой открыли форму
  useEffect(() => {
    if (!refs || prefilled.current) return;
    prefilled.current = true;
    setContact(contactFromCompany(refs.company));
    const n = needId ? refs.needs.find((x) => x.id === needId) : undefined;
    const v = vacancyId ? refs.vacancies.find((x) => x.id === vacancyId) : undefined;
    if (n) apply(fromNeed(n));
    else if (v) apply(fromVacancy(v));
  }, [refs, needId, vacancyId]);

  function onLinkChange(value: string) {
    setLink(value);
    if (!refs) return;
    const [kind, id] = value.split(":");
    if (kind === "need") {
      const n = refs.needs.find((x) => x.id === Number(id));
      if (n) apply(fromNeed(n));
    } else if (kind === "vacancy") {
      const v = refs.vacancies.find((x) => x.id === Number(id));
      if (v) apply(fromVacancy(v));
    }
  }

  const errs = {
    title: title.trim().length < 3 ? "Укажите позицию (не короче 3 символов)" : null,
    description: description.trim().length < 10 ? "Опишите предложение (не короче 10 символов)" : null,
    salary: salaryError(salaryFrom, salaryTo),
    contact: contact.trim().length < 3 ? "Укажите, как с вами связаться" : null,
  };
  const valid = !errs.title && !errs.description && !errs.salary && !errs.contact;
  const to = parseRub(salaryTo);
  const below = expect !== null && to !== null && to < expect;
  const quotaLeft = refs?.quota.left ?? null;

  async function submit() {
    setTried(true);
    setError(null);
    if (!valid) return;
    const [kind, id] = link.split(":");
    setBusy(true);
    try {
      const inv = await api<Invitation>("/employer/invitations", {
        body: {
          candidate_id: candidate.id,
          need_id: kind === "need" ? Number(id) : null,
          vacancy_id: kind === "vacancy" ? Number(id) : null,
          title: title.trim(),
          description: description.trim(),
          salary_from: parseRub(salaryFrom),
          salary_to: to,
          work_format: formats,
          contact_method: contact.trim(),
        },
      });
      toast(`Приглашение отправлено: ${candidate.display_name}`);
      onSent?.(inv);
      onClose();
    } catch (e) {
      const ae = e as ApiError;
      setError(ae.message);
      if (ae.status === 429 && refs) setRefs({ ...refs, quota: { ...refs.quota, left: 0 } });
    } finally {
      setBusy(false);
    }
  }

  const footer = (
    <>
      {quotaLeft !== null && (
        <span className="small muted" style={{ marginRight: "auto", alignSelf: "center" }}>
          Квота: осталось <b>{quotaLeft}</b> из {refs?.quota.limit} на неделе
        </span>
      )}
      <button className="btn btn-secondary" onClick={onClose} disabled={busy}>Отмена</button>
      <button className="btn btn-primary" onClick={submit} disabled={busy || !refs || quotaLeft === 0}>
        {busy ? "Отправляем…" : "Отправить приглашение"}
      </button>
    </>
  );

  return (
    <Modal title="Приглашение кандидату" onClose={onClose} footer={footer}>
      {!refs && !loadError && <Loading />}
      <ErrorBox error={loadError} />
      {refs && (
        <div className="stack">
          <div className="row small" style={{ gap: 8 }}>
            <span className="strong">{candidate.display_name}</span>
            {candidate.category && <span className="category">{candidate.category}</span>}
            <span className="muted">
              {expect !== null ? `ожидания от ${rub(expect)}` : "ожидания по зарплате не указаны или скрыты"}
            </span>
          </div>

          {quotaLeft === 0 && (
            <div className="alert alert-error">
              {refs.quota.reason && refs.quota.limit === 0 ? refs.quota.reason : <>
                Недельная квота приглашений исчерпана ({refs.quota.limit}). Квота заставляет выбирать, а не рассылать
                всем подряд — новые приглашения станут доступны через несколько дней.
              </>}
            </div>
          )}
          {quotaLeft !== 0 && refs.quota.reason && (
            <div className="alert alert-warn small">{refs.quota.reason}</div>
          )}

          {(refs.needs.length > 0 || refs.vacancies.length > 0) && (
            <Field label="Связать с потребностью или вакансией" hint="Поля заполнятся из выбранной записи — их можно изменить">
              <select className="select" value={link} onChange={(e) => onLinkChange(e.target.value)}>
                <option value="">Без привязки</option>
                {refs.needs.length > 0 && (
                  <optgroup label="Потребности">
                    {refs.needs.map((n) => <option key={n.id} value={`need:${n.id}`}>{n.title} · {n.category}</option>)}
                  </optgroup>
                )}
                {refs.vacancies.length > 0 && (
                  <optgroup label="Вакансии">
                    {refs.vacancies.map((v) => <option key={v.id} value={`vacancy:${v.id}`}>{v.title} · {v.category}</option>)}
                  </optgroup>
                )}
              </select>
            </Field>
          )}

          <Field label="Позиция *" error={tried ? errs.title : null}>
            <input className={`input ${tried && errs.title ? "invalid" : ""}`} value={title} maxLength={200}
              onChange={(e) => setTitle(e.target.value)} placeholder="Например, Python-разработчик в команду платежей" />
          </Field>
          <Field label="Описание предложения *" error={tried ? errs.description : null} hint="Задачи, команда, чем интересна позиция">
            <textarea className="textarea" value={description} maxLength={6000} onChange={(e) => setDescription(e.target.value)} />
          </Field>
          <SalaryFields from={salaryFrom} to={salaryTo} onFrom={setSalaryFrom} onTo={setSalaryTo} showError={tried} />
          {below && (
            <div className="alert alert-warn" role="alert">
              <span aria-hidden>⚠</span>
              <span>
                <b>Вилка ниже ожиданий кандидата — высокая вероятность отказа.</b> Кандидат ожидает от {rub(expect)}, а
                верхняя граница вилки — {rub(to)}. Отправить приглашение всё равно можно.
              </span>
            </div>
          )}
          <Field label="Формат работы">
            <ChipSelect options={d.work_formats} value={formats} onChange={setFormats} />
          </Field>
          <Field label="Способ связи *" error={tried ? errs.contact : null} hint="Кандидат увидит его вместе с приглашением">
            <input className={`input ${tried && errs.contact ? "invalid" : ""}`} value={contact} maxLength={255}
              onChange={(e) => setContact(e.target.value)} placeholder="Telegram @company_hr или hr@company.ru" />
          </Field>
          <ErrorBox error={error} />
        </div>
      )}
    </Modal>
  );
}
