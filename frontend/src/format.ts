export function rub(v: number | null | undefined): string {
  if (v === null || v === undefined) return "—";
  return `${v.toLocaleString("ru-RU")} ₽`;
}

export function salaryRange(from: number, to: number): string {
  return `${from.toLocaleString("ru-RU")} – ${to.toLocaleString("ru-RU")} ₽`;
}

export function date(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
}

export function dateShort(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit", year: "numeric" });
}

export function ago(iso: string | null | undefined): string {
  if (!iso) return "—";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "сегодня";
  if (days === 1) return "вчера";
  if (days < 30) return `${days} ${plural(days, "день", "дня", "дней")} назад`;
  const m = Math.floor(days / 30);
  return `${m} ${plural(m, "месяц", "месяца", "месяцев")} назад`;
}

export function plural(n: number, one: string, few: string, many: string): string {
  const n10 = n % 10;
  const n100 = n % 100;
  if (n10 === 1 && n100 !== 11) return one;
  if (n10 >= 2 && n10 <= 4 && (n100 < 10 || n100 >= 20)) return few;
  return many;
}

export function pct(x: number | null | undefined): string {
  if (x === null || x === undefined) return "—";
  return `${Math.round(x * 100)}%`;
}

export function years(y: number): string {
  if (!y) return "без опыта";
  const r = Math.round(y * 10) / 10;
  return `${r.toLocaleString("ru-RU")} ${plural(Math.floor(r), "год", "года", "лет")}`;
}
