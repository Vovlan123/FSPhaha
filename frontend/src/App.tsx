import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth";
import { DictProvider } from "./dict";
import { Layout } from "./components/Layout";
import { Loading, Toaster } from "./components/ui";
import type { Role } from "./types";
import Landing from "./pages/Landing";
import { Login, Register, Verify } from "./pages/Auth";
import HowItWorks from "./pages/HowItWorks";
import CandidateDashboard from "./pages/candidate/Dashboard";
import Onboarding from "./pages/candidate/Onboarding";
import TestRun from "./pages/candidate/TestRun";
import GradePage from "./pages/candidate/Grade";
import CandidateInvitations from "./pages/candidate/Invitations";
import CandidateVacancies from "./pages/candidate/Vacancies";
import CandidateTasks from "./pages/candidate/Tasks";
import CandidateSettings from "./pages/candidate/Settings";
import CandidateProfilePage from "./pages/candidate/Profile";
import EmployerDashboard from "./pages/employer/Dashboard";
import CompanyPage from "./pages/employer/Company";
import NeedsPage from "./pages/employer/Needs";
import NeedEdit from "./pages/employer/NeedEdit";
import SelectionPage from "./pages/employer/Selection";
import BankPage from "./pages/employer/Bank";
import CandidateCardPage from "./pages/employer/CandidateCard";
import EmployerInvitations from "./pages/employer/Invitations";
import EmployerVacancies from "./pages/employer/Vacancies";
import EmployerTasks from "./pages/employer/Tasks";

export function homeFor(role: Role): string {
  return role === "candidate" ? "/candidate" : "/employer";
}

function RequireRole({ role, children }: { role: Role; children: ReactNode }) {
  const { user, ready } = useAuth();
  const loc = useLocation();
  if (!ready) return <Loading />;
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  if (user.role !== role) return <Navigate to={homeFor(user.role)} replace />;
  return <>{children}</>;
}

function Home() {
  const { user, ready } = useAuth();
  if (!ready) return <Loading />;
  return user ? <Navigate to={homeFor(user.role)} replace /> : <Landing />;
}

export default function App() {
  return (
    <AuthProvider>
      <DictProvider>
        <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route element={<Layout />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
              <Route path="/verify" element={<Verify />} />
              <Route path="/how-it-works" element={<HowItWorks />} />

              <Route path="/candidate" element={<RequireRole role="candidate"><CandidateDashboard /></RequireRole>} />
              <Route path="/candidate/onboarding" element={<RequireRole role="candidate"><Onboarding /></RequireRole>} />
              <Route path="/candidate/test/:id" element={<RequireRole role="candidate"><TestRun /></RequireRole>} />
              <Route path="/candidate/grade" element={<RequireRole role="candidate"><GradePage /></RequireRole>} />
              <Route path="/candidate/invitations" element={<RequireRole role="candidate"><CandidateInvitations /></RequireRole>} />
              <Route path="/candidate/vacancies" element={<RequireRole role="candidate"><CandidateVacancies /></RequireRole>} />
              <Route path="/candidate/tasks" element={<RequireRole role="candidate"><CandidateTasks /></RequireRole>} />
              <Route path="/candidate/settings" element={<RequireRole role="candidate"><CandidateSettings /></RequireRole>} />
              <Route path="/candidate/profile" element={<RequireRole role="candidate"><CandidateProfilePage /></RequireRole>} />

              <Route path="/employer" element={<RequireRole role="employer"><EmployerDashboard /></RequireRole>} />
              <Route path="/employer/company" element={<RequireRole role="employer"><CompanyPage /></RequireRole>} />
              <Route path="/employer/needs" element={<RequireRole role="employer"><NeedsPage /></RequireRole>} />
              <Route path="/employer/needs/new" element={<RequireRole role="employer"><NeedEdit /></RequireRole>} />
              <Route path="/employer/needs/:id/edit" element={<RequireRole role="employer"><NeedEdit /></RequireRole>} />
              <Route path="/employer/needs/:id" element={<RequireRole role="employer"><SelectionPage /></RequireRole>} />
              <Route path="/employer/bank" element={<RequireRole role="employer"><BankPage /></RequireRole>} />
              <Route path="/employer/candidates/:id" element={<RequireRole role="employer"><CandidateCardPage /></RequireRole>} />
              <Route path="/employer/invitations" element={<RequireRole role="employer"><EmployerInvitations /></RequireRole>} />
              <Route path="/employer/vacancies" element={<RequireRole role="employer"><EmployerVacancies /></RequireRole>} />
              <Route path="/employer/tasks" element={<RequireRole role="employer"><EmployerTasks /></RequireRole>} />

              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
          <Toaster />
        </BrowserRouter>
      </DictProvider>
    </AuthProvider>
  );
}
