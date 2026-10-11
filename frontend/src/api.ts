// Тонкий клиент API: токен из localStorage, разбор ошибок FastAPI в понятное сообщение.

const TOKEN_KEY = "fsp_talent_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* приватный режим браузера — токен живёт только в памяти вкладки */
  }
}

export class ApiError extends Error {
  status: number;
  availableAt: string | null;
  constructor(status: number, message: string, availableAt: string | null = null) {
    super(message);
    this.status = status;
    this.availableAt = availableAt;
  }
}

type Detail = string | { message?: string; available_at?: string | null } | { msg: string; loc: (string | number)[] }[];

function parseDetail(detail: Detail | undefined, status: number): { message: string; availableAt: string | null } {
  if (!detail) return { message: `Ошибка ${status}`, availableAt: null };
  if (typeof detail === "string") return { message: detail, availableAt: null };
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => {
      const field = d.loc.filter((x) => x !== "body").join(".");
      const msg = d.msg.replace(/^Value error, /, "");
      return field ? `${field}: ${msg}` : msg;
    });
    return { message: msgs.join("; "), availableAt: null };
  }
  return { message: detail.message ?? `Ошибка ${status}`, availableAt: detail.available_at ?? null };
}

export async function api<T = unknown>(
  path: string,
  opts: { method?: string; body?: unknown; form?: FormData; blob?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method: opts.method ?? (body ? "POST" : "GET"), headers, body });
  } catch {
    throw new ApiError(0, "Сервер недоступен. Проверьте, что бэкенд запущен.");
  }
  if (!res.ok) {
    let detail: Detail | undefined;
    try {
      detail = (await res.json()).detail;
    } catch {
      /* тело без JSON */
    }
    const { message, availableAt } = parseDetail(detail, res.status);
    if (res.status === 401 && token) window.dispatchEvent(new Event("auth:expired"));
    throw new ApiError(res.status, message, availableAt);
  }
  if (opts.blob) return (await res.blob()) as T;
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function downloadFile(path: string, filename: string): Promise<void> {
  const blob = await api<Blob>(path, { blob: true });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
