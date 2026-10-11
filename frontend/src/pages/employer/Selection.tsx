import { useMemo, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../../api";
import InviteModal from "../../components/InviteModal";
import { ChipSelect, Empty, ErrorBox, Loading, ReasonList, Salary, ScoreRing, SkillTags, StatusBadge, Switch, toast, useLoad } from "../../components/ui";
import { useDict } from "../../dict";
import { ago, plural } from "../../format";
import type { CandidateSummary, CategoryCell, Need, SelectionResult } from "../../types";
import { BlueprintModal, CandidateMeta, CompanyGate, MiniStrength, ScoreParts, isActiveInvitation } from "./common";

// Фильтры применяются к сохранённой подборке на сервере и не пересчитывают её
const FLAGS: { key: string; label: string; hint: string }[] = [
  { key: "has_fsp", label: "Только с ФСП", hint: "Есть достижения в реестре ФСП" },
  { key: "confident_only", label: "Уверенно в грейде", hint: "Результат теста в верхней половине полосы грейда" },
  { key: "salary_fit", label: "Зарплата в вилке", hint: "Ожидания не выше верхней границы вилки" },
  { key: "pinned_only", label: "Только шорт-лист", hint: "Кандидаты, которых вы закрепили" },
  { key: "new_only", label: "Только новые", hint: "Появились при последнем пересчёте" },
];

const KIND: Record<string, { label: string; cls: string }> = {
  main: { label: "Основная", cls: "badge-solid" },
  adjacent: { label: "Соседний грейд", cls: "badge-blue" },
  related: { label: "Смежная специализация", cls: "badge-amber" },
};

function NeedHeader({ need, total, onRecompute, recomputing, onBlueprint }: {
  need: Need; total: number; onRecompute: () => void; recomputing: boolean; onBlueprint: () => void;
}) {
  const d = useDict();
  return (
    <div className="card stack">
      <div className="row-between" style={{ alignItems: "flex-start" }}>
        <div className="stack-sm" style={{ minWidth: 0 }}>
          <Link to="/employer/needs" className="small">← Все потребности</Link>
          <div className="row" style={{ gap: 10 }}>
            <h1>{need.title}</h1>
            {need.category && <span className="category">{need.category}</span>}
          </div>
        </div>
        <div className="stack-sm" style={{ alignItems: "flex-end" }}>
          <Salary from={need.salary_from} to={need.salary_to} large />
          <span className="small muted">
            {need.work_format.length ? need.work_format.map((f) => d.label(d.work_formats, f)).join(", ") : "любой формат"}
            {need.city ? ` · ${need.city}` : ""}
          </span>
        </div>
      </div>
      <div className="stack-sm">
        <div className="row small" style={{ gap: 8 }}>
          <span className="strong" style={{ minWidth: 110 }}>Обязательно:</span>
          {need.stack_must.length ? <SkillTags skills={need.stack_must} /> : <span className="muted">не указано</span>}
        </div>
        {need.stack_nice.length > 0 && (
          <div className="row small" style={{ gap: 8 }}>
            <span className="strong" style={{ minWidth: 110 }}>Желательно:</span>
            <SkillTags skills={need.stack_nice} />
          </div>
        )}
      </div>
      <div className="row-between">
        <span className="small muted">
          Подборка сформирована {ago(need.selection_at)} · {total} {plural(total, "кандидат", "кандидата", "кандидатов")} · в шорт-листе {need.pinned ?? 0}
        </span>
        <div className="row">
          <button className="btn btn-ghost btn-sm" onClick={onBlueprint}>Какие задания получит кандидат</button>
          <Link to={`/employer/needs/${need.id}/edit`} className="btn btn-secondary btn-sm">Изменить потребность</Link>
          <button className="btn btn-primary btn-sm" onClick={onRecompute} disabled={recomputing}
            title="Шорт-лист сохранится, новые кандидаты получат метку «новый»">
            {recomputing ? "Пересчитываем…" : "Пересчитать подборку"}
          </button>
        </div>
      </div>
    </div>
  );
}

function RecommendedCategories({ cats }: { cats: CategoryCell[] }) {
  const nav = useNavigate();
  return (
    <div className="stack-sm">
      <h3>Рекомендованные категории</h3>
      <div className="grid grid-auto">
        {cats.map((c) => {
          const k = KIND[c.kind ?? ""] ?? { label: c.kind ?? "", cls: "badge-grey" };
          return (
            <button
              key={`${c.kind}-${c.specialization}-${c.grade}`}
              type="button"
              className="card card-tight card-link rec-cat stack-sm"
              onClick={() => nav(`/employer/bank?specialization=${c.specialization}&grade=${c.grade}`)}
              title="Открыть категорию в банке кандидатов"
            >
              <div className="row-between">
                <span className={`badge ${k.cls}`}>{k.label}</span>
                <span className="n">{c.count}</span>
              </div>
              <div className="strong">{c.label}</div>
              <div className="tiny muted">{c.note}{c.with_fsp ? ` · с ФСП: ${c.with_fsp}` : ""}</div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function SelectionRow({ c, need, pinning, onPin, onInvite }: {
  c: CandidateSummary; need: Need; pinning: boolean; onPin: () => void; onInvite: () => void;
}) {
  const d = useDict();
  const have = new Set(c.stack);
  const needStack = [...need.stack_must, ...need.stack_nice];
  const matched = needStack.filter((s) => have.has(s));
  const missing = need.stack_must.filter((s) => !have.has(s));
  const others = Array.from(have).filter((s) => !needStack.includes(s));
  const inv = c.invitation;
  const cardLink = `/employer/candidates/${c.id}?need=${need.id}`;

  return (
    <article className={`card cand ${c.pinned ? "pinned" : ""}`}>
      <div className="stack-sm" style={{ alignItems: "center" }}>
        <ScoreRing value={c.score ?? 0} />
        {c.rank ? <span className="tiny muted">#{c.rank}</span> : null}
      </div>

      <div className="stack-sm" style={{ minWidth: 0 }}>
        <div className="row" style={{ gap: 8 }}>
          <Link to={cardLink} className="cand-name">{c.display_name}</Link>
          <span className="category">{c.category}</span>
          {c.is_new && <span className="badge badge-amber">новый</span>}
          {c.pinned && <span className="badge badge-solid">★ шорт-лист</span>}
          {c.has_fsp && <span className="badge" title={c.fsp_top ?? undefined}>ФСП</span>}
        </div>
        <CandidateMeta c={c} />

        <div>
          <div className="tiny muted strong" style={{ marginBottom: 4 }}>
            Стек под потребность · <span style={{ color: "var(--green)" }}>✓ подтверждено тестом</span> · <span style={{ color: "var(--amber)" }}>⚠ тест не подтвердил</span> · <span style={{ color: "var(--red)" }}>нет в профиле</span>
          </div>
          {matched.length || missing.length ? (
            <SkillTags skills={matched} verified={c.verified_skills} refuted={c.refuted_skills} missing={missing} />
          ) : (
            <span className="small muted">Стек потребности не задан</span>
          )}
          {others.length > 0 && (
            <div className="tiny muted" style={{ marginTop: 4 }}>
              Ещё в профиле: {others.slice(0, 8).map((s) => d.skill(s)).join(", ")}
              {others.length > 8 ? ` и ещё ${others.length - 8}` : ""}
            </div>
          )}
        </div>

        <div>
          <div className="tiny muted strong" style={{ marginBottom: 4 }}>Почему в подборке</div>
          <ReasonList reasons={c.reasons ?? []} />
        </div>

        <MiniStrength s={c.strength} />

        {c.components && (
          <details className="why">
            <summary>Из чего складывается балл {Math.round(c.score ?? 0)}</summary>
            <div style={{ marginTop: 8 }}><ScoreParts components={c.components} /></div>
          </details>
        )}
      </div>

      <div className="cand-actions">
        <button className={`btn btn-sm ${c.pinned ? "btn-primary" : "btn-secondary"}`} onClick={onPin} disabled={pinning} aria-pressed={!!c.pinned}>
          {c.pinned ? "★ В шорт-листе" : "☆ В шорт-лист"}
        </button>
        <Link to={cardLink} className="btn btn-secondary btn-sm">Профиль</Link>
        {inv && isActiveInvitation(inv.status) ? (
          <div className="small muted" style={{ textAlign: "center" }}>
            <StatusBadge kind="invitation" status={inv.status} />
            <div className="tiny" style={{ marginTop: 4 }}>ждём ответа кандидата</div>
          </div>
        ) : inv?.status === "accepted" ? (
          <div className="small" style={{ textAlign: "center" }}>
            <StatusBadge kind="invitation" status="accepted" />
            <div className="tiny muted" style={{ marginTop: 4 }}>контакты в профиле</div>
          </div>
        ) : (
          <>
            <button className="btn btn-success btn-sm" onClick={onInvite}>{inv ? "Пригласить снова" : "Пригласить"}</button>
            {inv && (
              <div className="tiny muted" style={{ textAlign: "center" }}>
                прошлое: <StatusBadge kind="invitation" status={inv.status} />
              </div>
            )}
          </>
        )}
      </div>
    </article>
  );
}

function SelectionView() {
  const { id } = useParams();
  const needId = Number(id);
  const d = useDict();
  const [params, setParams] = useSearchParams();
  const [recomputing, setRecomputing] = useState(false);
  const [pinning, setPinning] = useState<number | null>(null);
  const [inviting, setInviting] = useState<CandidateSummary | null>(null);
  const [blueprint, setBlueprint] = useState(false);

  const stackSel = (params.get("stack") ?? "").split(",").filter(Boolean);
  const minScore = params.get("min_score") ?? "";
  const activeFlags = FLAGS.filter((f) => params.get(f.key) === "1").map((f) => f.key);
  const hasFilters = stackSel.length > 0 || activeFlags.length > 0 || !!minScore;

  const apiQs = useMemo(() => {
    const q = new URLSearchParams();
    const stack = params.get("stack");
    if (stack) q.set("stack", stack);
    for (const f of FLAGS) if (params.get(f.key) === "1") q.set(f.key, "true");
    const ms = params.get("min_score");
    if (ms) q.set("min_score", ms);
    return q.toString();
  }, [params]);

  const { data, error, loading, reload, setData } = useLoad(
    () => api<SelectionResult>(`/employer/needs/${needId}/selection${apiQs ? `?${apiQs}` : ""}`),
    [needId, apiQs],
  );

  function setParam(key: string, value: string | null) {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  }

  async function recompute() {
    setRecomputing(true);
    try {
      // POST пересчитывает и сохраняет подборку; затем перечитываем её с текущими фильтрами
      await api(`/employer/needs/${needId}/selection`, { method: "POST" });
      await reload();
      toast("Подборка пересчитана: шорт-лист сохранён, новые кандидаты отмечены");
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setRecomputing(false);
    }
  }

  async function togglePin(c: CandidateSummary) {
    setPinning(c.id);
    try {
      const r = await api<{ pinned: boolean }>(`/employer/needs/${needId}/selection/${c.id}/pin`, { body: { pinned: !c.pinned } });
      setData((prev) =>
        prev && {
          ...prev,
          need: { ...prev.need, pinned: Math.max(0, (prev.need.pinned ?? 0) + (r.pinned === !!c.pinned ? 0 : r.pinned ? 1 : -1)) },
          items: prev.items.map((x) => (x.id === c.id ? { ...x, pinned: r.pinned } : x)),
        },
      );
      toast(r.pinned ? `${c.display_name} — в шорт-листе` : `${c.display_name} убран из шорт-листа`);
    } catch (e) {
      toast((e as Error).message);
    } finally {
      setPinning(null);
    }
  }

  if (!data && loading) return <Loading />;
  if (!data) return <ErrorBox error={error} />;

  const { need } = data;
  const skillOptions = [...need.stack_must, ...need.stack_nice].map((s) => ({ code: s, label: d.skill(s) }));

  return (
    <div className="stack-lg">
      <NeedHeader need={need} total={data.total} onRecompute={recompute} recomputing={recomputing} onBlueprint={() => setBlueprint(true)} />

      {data.categories.length > 0 && <RecommendedCategories cats={data.categories} />}

      <div className="sidebar-layout">
        <aside className="card stack emp-sticky" aria-label="Фильтры подборки">
          <div className="row-between">
            <h3>Фильтры</h3>
            {hasFilters && (
              <button className="btn btn-ghost btn-sm" onClick={() => setParams(new URLSearchParams(), { replace: true })}>Сбросить</button>
            )}
          </div>
          <p className="tiny muted" style={{ marginTop: -8 }}>Применяются к сохранённой подборке — она не пересчитывается и не теряется.</p>
          {skillOptions.length > 0 && (
            <div className="field">
              <label>Владеет навыками</label>
              <ChipSelect options={skillOptions} value={stackSel} onChange={(v) => setParam("stack", v.join(",") || null)} />
              <span className="hint">Заявлено или подтверждено тестом — все выбранные</span>
            </div>
          )}
          <div>
            {FLAGS.map((f) => (
              <Switch key={f.key} label={f.label} hint={f.hint} checked={activeFlags.includes(f.key)} onChange={(v) => setParam(f.key, v ? "1" : null)} />
            ))}
          </div>
          <div className="field">
            <label htmlFor="min-score">Балл соответствия</label>
            <select id="min-score" className="select" value={minScore} onChange={(e) => setParam("min_score", e.target.value || null)}>
              <option value="">Любой</option>
              {[50, 60, 70, 80].map((v) => <option key={v} value={v}>от {v}</option>)}
            </select>
          </div>
        </aside>

        <section className="stack" aria-live="polite">
          <div className="row-between">
            <div className="small">
              Показано <b>{data.shown}</b> из <b>{data.total}</b> · по убыванию балла соответствия
              {loading && <span className="muted"> · обновляем…</span>}
            </div>
            <span className="tiny muted">Балл = 40% стек + 25% категория + 20% сила профиля + 15% условия</span>
          </div>
          <ErrorBox error={error} />

          <div className={`stack ${loading ? "emp-busy" : ""}`}>
            {data.total === 0 ? (
              <div className="card">
                <Empty icon="◎" title="В подборке пока никого">
                  <p>
                    Нет кандидатов с подтверждённым грейдом рядом с «{need.category}», которые набирают хотя бы 30 баллов.
                    Ослабьте обязательный стек, расширьте вилку или посмотрите соседние категории.
                  </p>
                  <div className="row" style={{ justifyContent: "center", marginTop: 14 }}>
                    <Link to={`/employer/needs/${need.id}/edit`} className="btn btn-primary">Изменить потребность</Link>
                    <Link to={`/employer/bank?specialization=${need.specialization}`} className="btn btn-secondary">Открыть банк</Link>
                  </div>
                </Empty>
              </div>
            ) : data.items.length === 0 ? (
              <div className="card">
                <Empty icon="⌕" title="Под выбранные фильтры никто не подходит">
                  <p>Подборка из {data.total} {plural(data.total, "кандидата", "кандидатов", "кандидатов")} сохранена — ослабьте фильтры, чтобы увидеть её.</p>
                  <div style={{ marginTop: 14 }}>
                    <button className="btn btn-secondary" onClick={() => setParams(new URLSearchParams(), { replace: true })}>Сбросить фильтры</button>
                  </div>
                </Empty>
              </div>
            ) : (
              data.items.map((c) => (
                <SelectionRow
                  key={c.id}
                  c={c}
                  need={need}
                  pinning={pinning === c.id}
                  onPin={() => togglePin(c)}
                  onInvite={() => setInviting(c)}
                />
              ))
            )}
          </div>
        </section>
      </div>

      {inviting && (
        <InviteModal
          candidate={{ id: inviting.id, display_name: inviting.display_name, category: inviting.category, salary_expect_min: inviting.salary_expect_min }}
          needId={need.id}
          onClose={() => setInviting(null)}
          onSent={(inv) =>
            setData((prev) => prev && { ...prev, items: prev.items.map((x) => (x.id === inviting.id ? { ...x, invitation: { id: inv.id, status: inv.status } } : x)) })
          }
        />
      )}
      {blueprint && (
        <BlueprintModal path={`/employer/needs/${need.id}/blueprint`} title="Какие задания получит кандидат" onClose={() => setBlueprint(false)} />
      )}
    </div>
  );
}

export default function SelectionPage() {
  return (
    <CompanyGate>
      <SelectionView />
    </CompanyGate>
  );
}
