import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { api } from "../api";
import { useAuth } from "../auth";

const CANDIDATE_NAV = [
  { to: "/candidate", label: "Главная", end: true },
  { to: "/candidate/invitations", label: "Приглашения", badge: "invitations" },
  { to: "/candidate/vacancies", label: "Вакансии" },
  { to: "/candidate/tasks", label: "Задания" },
  { to: "/candidate/grade", label: "Грейд и тесты" },
  { to: "/candidate/settings", label: "Настройки" },
];
const EMPLOYER_NAV = [
  { to: "/employer", label: "Главная", end: true },
  { to: "/employer/needs", label: "Подбор" },
  { to: "/employer/bank", label: "Банк кандидатов" },
  { to: "/employer/invitations", label: "Приглашения" },
  { to: "/employer/vacancies", label: "Вакансии" },
  { to: "/employer/tasks", label: "Задания" },
  { to: "/employer/company", label: "Компания" },
];

export function Logo() {
  return (
    <Link to="/" className="logo" aria-label="ФСП Талант — на главную">
      <img src="/favicon.svg" width={34} height={34} alt="" />
      <span>
        ФСП Талант
        <small>подбор с подтверждённым профилем</small>
      </span>
    </Link>
  );
}

function initials(email: string) {
  const name = email.split("@")[0] || "?";
  const parts = name.split(/[._-]+/).filter(Boolean);
  const letters = (parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? parts[0]?.[1] ?? "");
  return letters.toUpperCase() || "?";
}

export function Layout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const [newInv, setNewInv] = useState(0);

  useEffect(() => {
    if (user?.role !== "candidate") return;
    api<{ new_invitations: number }>("/candidate/status")
      .then((s) => setNewInv(s.new_invitations))
      .catch(() => undefined);
  }, [user, loc.pathname]);

  const items = user?.role === "candidate" ? CANDIDATE_NAV : user?.role === "employer" ? EMPLOYER_NAV : [];
  const onLogin = loc.pathname.startsWith("/login");
  const onRegister = loc.pathname.startsWith("/register");
  return (
    <>
      <a href="#content" className="skip-link">К содержанию</a>
      <header className="app-header">
        <div className="app-header-inner">
          <Logo />
          <nav className="nav" aria-label="Основная навигация">
            {items.map((i) => (
              <NavLink key={i.to} to={i.to} end={i.end} className={({ isActive }) => (isActive ? "active" : "")}>
                {i.label}
                {"badge" in i && newInv > 0 && <span className="dot" aria-label={`${newInv} новых`}>{newInv}</span>}
              </NavLink>
            ))}
          </nav>
          {user ? (
            <div className="user-box">
              <span className="avatar" aria-hidden>{initials(user.email)}</span>
              <span>
                <span className="email">{user.email}</span>
                <br />
                <span className="role">{user.role === "candidate" ? "Кандидат" : "Работодатель"}</span>
              </span>
              <button
                className="btn btn-light btn-sm"
                onClick={() => {
                  logout();
                  nav("/");
                }}
              >
                Выйти
              </button>
            </div>
          ) : (
            <div className="row">
              <Link to="/how-it-works" className="btn btn-light btn-sm">Как это работает</Link>
              {!onLogin && <Link to="/login" className="btn btn-light btn-sm">Войти</Link>}
              {!onRegister && <Link to="/register" className="btn btn-white btn-sm">Регистрация</Link>}
            </div>
          )}
        </div>
      </header>
      <main className="main" id="content">
        <Outlet />
      </main>
    </>
  );
}
