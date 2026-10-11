import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Dictionaries } from "./types";

type Dict = Dictionaries & {
  spec: (code?: string | null) => string;
  specShort: (code?: string | null) => string;
  grade: (code?: string | null) => string;
  skill: (code: string) => string;
  label: (list: { code: string; label: string }[], code?: string | null) => string;
  status: (kind: string, code: string) => string;
};

const DictCtx = createContext<Dict | null>(null);

export function DictProvider({ children }: { children: ReactNode }) {
  const [d, setD] = useState<Dictionaries | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api<Dictionaries>("/meta/dictionaries")
      .then(setD)
      .catch((e) => setError(e.message));
  }, []);
  if (error)
    return (
      <div className="main">
        <div className="alert alert-error">Не удалось загрузить справочники: {error}</div>
      </div>
    );
  if (!d)
    return (
      <div className="loading">
        <div className="spinner" />
      </div>
    );
  const value: Dict = {
    ...d,
    spec: (c) => d.specializations.find((s) => s.code === c)?.label ?? c ?? "—",
    specShort: (c) => d.specializations.find((s) => s.code === c)?.short ?? c ?? "—",
    grade: (c) => d.grades.find((g) => g.code === c)?.label ?? c ?? "—",
    skill: (c) => d.skills[c] ?? c,
    label: (list, c) => list.find((x) => x.code === c)?.label ?? c ?? "—",
    status: (kind, c) => d.status_labels[kind]?.[c] ?? c,
  };
  return <DictCtx.Provider value={value}>{children}</DictCtx.Provider>;
}

export function useDict(): Dict {
  const ctx = useContext(DictCtx);
  if (!ctx) throw new Error("useDict вне DictProvider");
  return ctx;
}
