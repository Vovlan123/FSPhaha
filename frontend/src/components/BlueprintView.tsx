import { useDict } from "../dict";
import type { Blueprint } from "../types";
import { CodeBlock } from "./ui";

const FMT: Record<string, string> = { output: "что выведет код", calc: "вычисление", bug: "найти ошибку", concept: "понимание" };

/** План теста под вакансию/потребность: какие шаблоны получат приоритет и два разных экземпляра одного шаблона. */
export default function BlueprintView({ bp }: { bp: Blueprint }) {
  const d = useDict();
  return (
    <div className="stack">
      <div className="alert alert-brand">
        <span aria-hidden>ⓘ</span>
        <span>
          Работодатель не пишет тест вручную. Из стека и грейда система выбирает шаблоны банка, которые лучше всего
          различают кандидатов около порога грейда «{d.grade(bp.grade)}» (θ = {bp.cutoff}). Каждый кандидат получает
          свой экземпляр: числа, имена и порядок вариантов меняются, а сложность остаётся одинаковой. Тест адаптивный:
          {" "}{bp.rules.min_items}–{bp.rules.max_items} вопросов, {bp.rules.time_limit_sec} секунд на вопрос.
        </span>
      </div>
      <div className="row small">
        <span className="strong">Покрыто банком:</span>
        {bp.covered_topics.length ? bp.covered_topics.map((t) => <span key={t.code} className="skill verified">✓ {t.label}</span>) : <span className="muted">—</span>}
      </div>
      {bp.uncovered_topics.length > 0 && (
        <div className="row small">
          <span className="strong">Проверяется регулярными заданиями:</span>
          {bp.uncovered_topics.map((t) => <span key={t.code} className="skill">{t.label}</span>)}
        </div>
      )}
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>Шаблон</th><th>Темы</th><th>Формат</th><th>Сложность b</th><th>Относительно порога</th></tr>
          </thead>
          <tbody>
            {bp.plan.map((p) => (
              <tr key={p.template_id}>
                <td>
                  <div className="strong">{p.title}</div>
                  <div className="tiny muted mono">{p.template_id} · ~{p.variants.toLocaleString("ru-RU")} вариантов</div>
                </td>
                <td>
                  <div className="chips">
                    {p.topics.map((t) => <span key={t.code} className={`skill ${p.relevant ? "verified" : ""}`}>{t.label}</span>)}
                  </div>
                </td>
                <td className="small">{FMT[p.fmt] ?? p.fmt}</td>
                <td className="mono small">{p.b.toFixed(2)}</td>
                <td><span className={`badge ${p.difficulty === "около порога" ? "badge-green" : "badge-grey"}`}>{p.difficulty}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {bp.samples.map((s) => (
        <div key={s.template_id} className="card card-tight">
          <h4>Пример: «{s.title}» — два кандидата получают разные экземпляры</h4>
          <div className="grid grid-2" style={{ marginTop: 10 }}>
            {s.instances.map((inst, i) => (
              <div key={i} className="stack-sm">
                <div className="badge badge-grey">Кандидат {i === 0 ? "А" : "Б"}</div>
                <div className="small strong">{inst.stem}</div>
                {inst.code && <CodeBlock code={inst.code} lang={inst.code_lang} />}
                <ol className="small" style={{ margin: 0, paddingLeft: 20 }}>
                  {inst.options.map((o, j) => <li key={j} className="mono">{o}</li>)}
                </ol>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
