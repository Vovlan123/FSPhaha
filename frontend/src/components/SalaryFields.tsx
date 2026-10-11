// Обязательная зарплатная вилка «от – до» с проверкой на клиенте (сервер дублирует её и отвечает 422).
import { salaryRange } from "../format";

/** Значение поля хранится строкой, чтобы его можно было очистить. */
export function parseRub(v: string): number | null {
  const n = Number(v.replace(/\s/g, ""));
  return v.trim() && Number.isFinite(n) ? Math.round(n) : null;
}

/** Текст ошибки вилки или null, если вилка корректна. */
export function salaryError(from: string, to: string): string | null {
  const f = parseRub(from);
  const t = parseRub(to);
  if (f === null || t === null) return "Укажите зарплату «от» и «до» — вилка обязательна";
  if (f < 1000 || t < 1000) return "Минимум 1 000 ₽";
  if (f > t) return "Зарплата «от» не может быть больше «до»";
  return null;
}

export default function SalaryFields({
  from,
  to,
  onFrom,
  onTo,
  showError,
  label = "Зарплатная вилка, ₽/мес",
}: {
  from: string;
  to: string;
  onFrom: (v: string) => void;
  onTo: (v: string) => void;
  showError?: boolean;
  label?: string;
}) {
  const err = salaryError(from, to);
  const visibleErr = showError || (from.trim() && to.trim()) ? err : null;
  const f = parseRub(from);
  const t = parseRub(to);
  return (
    <div className="field">
      <label>{label} *</label>
      <div className="grid grid-2" style={{ gap: 10 }}>
        <input
          className={`input ${visibleErr ? "invalid" : ""}`}
          type="number"
          inputMode="numeric"
          min={1000}
          step={5000}
          placeholder="от"
          aria-label="Зарплата от"
          value={from}
          onChange={(e) => onFrom(e.target.value)}
        />
        <input
          className={`input ${visibleErr ? "invalid" : ""}`}
          type="number"
          inputMode="numeric"
          min={1000}
          step={5000}
          placeholder="до"
          aria-label="Зарплата до"
          value={to}
          onChange={(e) => onTo(e.target.value)}
        />
      </div>
      {visibleErr ? (
        <span className="error" role="alert">{visibleErr}</span>
      ) : f !== null && t !== null ? (
        <span className="hint">{salaryRange(f, t)} в месяц</span>
      ) : (
        <span className="hint">Вилка обязательна: кандидат видит её до ответа</span>
      )}
    </div>
  );
}
