// Типы ответов API (подмножество полей, которые использует интерфейс).

export type Role = "candidate" | "employer";
export type User = { id: number; email: string; role: Role };

export type Grade = { code: string; label: string; cutoff: number; years: string; description: string };
export type Specialization = { code: string; label: string; short: string; description: string; skills: string[] };
export type CodeLabel = { code: string; label: string };

export type Dictionaries = {
  grades: Grade[];
  specializations: Specialization[];
  skills: Record<string, string>;
  work_formats: CodeLabel[];
  industries: CodeLabel[];
  soft_skills: CodeLabel[];
  roles: CodeLabel[];
  decline_reasons: CodeLabel[];
  complaint_reasons: CodeLabel[];
  job_statuses: CodeLabel[];
  fsp_levels: Record<string, string>;
  fsp_results: Record<string, string>;
  fsp_disciplines: Record<string, string>;
  status_labels: Record<string, Record<string, string>>;
};

export type Reason = { kind: "plus" | "minus" | "info"; text: string };

export type Achievement = {
  event_id: string;
  event_name: string;
  discipline: string;
  level: string;
  result: string;
  place: number | null;
  team_name?: string;
  team_role?: string;
  date: string;
  headline?: string;
  discipline_label?: string;
  level_label?: string;
  result_label?: string;
  contribution?: number;
};

export type Fsp = {
  linked: boolean;
  visible: boolean;
  fsp_id?: string | null;
  score: number;
  achievements: Achievement[];
  fetched_at?: string | null;
  status_text: string | null;
};

export type Strength = { P: number; T: number; F: number; A: number; activity: { count?: number; avg?: number } };

export type CandidateProfile = {
  id: number;
  anon_code: string;
  email: string;
  full_name: string;
  phone: string;
  telegram: string;
  contact_email: string;
  city: string;
  relocation: boolean;
  about: string;
  experience_years: number;
  roles: string[];
  soft_skills: string[];
  industries: string[];
  specialization: string | null;
  stack: string[];
  work_format: string[];
  salary_expect_min: number | null;
  grade: string | null;
  theta: number | null;
  theta_se: number | null;
  category: string | null;
  job_status: string;
  consent_publish: boolean;
  privacy: { show_name: boolean; show_salary: boolean; show_fsp: boolean; show_tasks: boolean; hidden_companies: string[] };
  resume_source: string;
  fsp: Fsp;
};

export type Availability = { grade: string; allowed: boolean; reason: string | null; available_at: string | null };

export type CandidateStatus = {
  steps: { profile: boolean; survey: boolean; test: boolean; publish: boolean; fsp: boolean };
  onboarding_complete: boolean;
  category: string | null;
  specialization: string | null;
  grade: string | null;
  grade_label: string | null;
  theta: number | null;
  theta_se: number | null;
  grade_changed_at: string | null;
  next_grade_change_at: string | null;
  strength: Strength;
  visible_to_employers: boolean;
  job_status: string;
  active_attempt_id: number | null;
  availability: Availability[];
  new_invitations: number;
  verified_skills: CodeLabel[];
  fsp: Fsp;
  next_task_at: string | null;
};

export type TestItem = {
  id: number;
  order: number;
  stem: string;
  code: string | null;
  code_lang: string | null;
  options: string[];
  time_limit_sec: number;
  served_at: string;
  topic_labels: string[];
};

export type Attempt = {
  id: number;
  specialization: string;
  declared_grade: string;
  status: string;
  answered: number;
  min_items: number;
  max_items: number;
  started_at: string;
  finished_at: string | null;
  current_item: TestItem | null;
  theta?: number;
  se?: number;
  n_items?: number;
  result?: "confirmed" | "confirmed_plus" | "not_confirmed";
  upgrade_grade?: string | null;
  suggested_grade?: string | null;
  upgrade_accepted?: boolean;
  correct?: number;
  timed_out?: number;
  topics?: { topic: string; label: string; correct: number; total: number; expected: number; status: "verified" | "refuted" | "neutral" }[];
  trace?: { order: number; is_correct: boolean; theta: number; se: number; b: number }[];
};

export type Company = {
  id: number;
  name: string;
  industry: string;
  city: string;
  website: string;
  description: string;
  size: string;
};

export type Invitation = {
  id: number;
  title: string;
  description: string;
  salary_from: number;
  salary_to: number;
  work_format: string[];
  contact_method: string;
  status: string;
  status_label: string;
  below_expectations: boolean;
  decline_reason: string | null;
  decline_reason_label: string | null;
  decline_comment: string | null;
  expected_salary: number | null;
  created_at: string;
  viewed_at: string | null;
  responded_at: string | null;
  expires_at: string;
  need_id: number | null;
  vacancy_id: number | null;
  complaint_reason?: string | null;
  complaint_comment?: string | null;
  complaint_at?: string | null;
  company_verified?: boolean;
  trust?: TrustSignals;
  company: Company;
  candidate?: {
    id: number;
    anon_code: string;
    category: string | null;
    display_name: string;
    contacts: Contacts | null;
  };
};

export type Contacts = { full_name: string; email: string; phone: string; telegram: string };

export type Vacancy = {
  id: number;
  title: string;
  description: string;
  specialization: string;
  grade: string;
  category: string | null;
  stack: string[];
  stack_labels: string[];
  work_format: string[];
  city: string;
  salary_from: number;
  salary_to: number;
  status: string;
  created_at: string;
  company: Company;
  match?: { score: number; reasons: Reason[] } | null;
  application?: { id: number; status: string } | null;
  applications?: number;
  new_applications?: number;
};

export type Application = {
  id: number;
  status: string;
  status_label: string;
  cover_letter: string;
  match_score: number | null;
  created_at: string;
  vacancy: Vacancy;
  candidate?: { id: number; anon_code: string; display_name: string; category: string | null; contacts: Contacts };
};

export type Assignment = {
  id: number;
  status: string;
  status_label: string;
  answer: string;
  auto_score: number | null;
  rubric_hits: string[];
  employer_score: number | null;
  assigned_at: string;
  submitted_at: string | null;
  task?: { id: number; title: string; body: string; kind: string; company: string; rubric_points: string[] };
  candidate?: { id: number; anon_code: string; category: string | null };
  invitation?: { id: number; status: string } | null;
};

export type CandidateSummary = {
  id: number;
  anon_code: string;
  display_name: string;
  specialization: string;
  grade: string;
  category: string;
  city: string;
  relocation: boolean;
  experience_years: number;
  work_format: string[];
  salary_expect_min: number | null;
  stack: string[];
  verified_skills: string[];
  refuted_skills?: string[];
  has_fsp: boolean;
  fsp_top: string | null;
  job_status: string;
  strength: Strength;
  invitation?: { id: number; status: string } | null;
  score?: number;
  components?: Record<string, number>;
  reasons?: Reason[];
  pinned?: boolean;
  is_new?: boolean;
  rank?: number;
};

export type CandidateCard = CandidateSummary & {
  about: string;
  roles: string[];
  soft_skills: string[];
  industries: string[];
  theta: number | null;
  theta_se: number | null;
  grade_changed_at: string | null;
  verified_topics: { topic: string; label: string; correct: number; total: number; expected?: number; verified: boolean; refuted?: boolean }[];
  fsp: Fsp;
  tasks: { title: string; kind: string; auto_score: number | null; employer_score: number | null; submitted_at: string | null }[];
  contacts_unlocked: boolean;
  contacts: Contacts | null;
  last_invitation: { id: number; status: string; created_at: string } | null;
};

export type Need = {
  id: number;
  title: string;
  description: string;
  team_about: string;
  specialization: string;
  grade: string;
  category: string | null;
  stack_must: string[];
  stack_nice: string[];
  work_format: string[];
  city: string;
  salary_from: number;
  salary_to: number;
  selection_at: string | null;
  created_at?: string;
  updated_at?: string;
  selection_size?: number;
  pinned?: number;
};

export type CategoryCell = {
  specialization: string;
  grade: string;
  label: string;
  count: number;
  with_fsp: number;
  median_salary?: number | null;
  kind?: string;
  note?: string;
};

export type Blueprint = {
  specialization: string;
  grade: string;
  cutoff: number;
  plan: {
    template_id: string;
    title: string;
    pool: string;
    fmt: string;
    topics: CodeLabel[];
    relevant: boolean;
    a: number;
    b: number;
    difficulty: string;
    variants: number;
  }[];
  covered_topics: CodeLabel[];
  uncovered_topics: CodeLabel[];
  samples: { template_id: string; title: string; instances: { stem: string; code: string | null; code_lang: string | null; options: string[] }[] }[];
  rules: { min_items: number; max_items: number; time_limit_sec: number; core_share_max: number };
};

// ---------- кабинет работодателя

export type VerificationCheck = { code: string; ok: boolean; text: string };

export type EmployerCompany = Company & {
  contact_email: string;
  contact_telegram: string;
  contact_phone: string;
  invite_quota_week: number;
  complete: boolean;
  inn: string;
  verified: boolean;
  verified_at: string | null;
  verification_checks: VerificationCheck[];
  webhook_url: string;
  webhook_secret: string;
  verification_ok?: boolean;
};

export type Quota = { limit: number; used: number; left: number; verified?: boolean; reason?: string | null; full_limit?: number };

export type WebhookDelivery = {
  id: number;
  event: string;
  status: "pending" | "delivered" | "failed";
  response_code: number | null;
  error: string | null;
  attempts: number;
  created_at: string;
  delivered_at: string | null;
};

export type Integrations = {
  webhook_url: string;
  webhook_secret: string;
  events: string[];
  signature_header: string;
  deliveries: WebhookDelivery[];
};

export type TrustSignals = {
  company_verified: boolean;
  accept_rate: number | null;
  invitations_90d: number;
  complaints: number;
  mass_mailing: number;
  category_median: number | null;
  below_market: boolean;
  warnings: string[];
};

export type EmployerDashboard = {
  company: EmployerCompany;
  categories: CategoryCell[];
  invitations: Record<string, number>;
  quota: Quota;
  new_applications: number;
  needs: number;
};

export type SelectionResult = { need: Need; categories: CategoryCell[]; total: number; shown: number; items: CandidateSummary[] };

export type ParsedNeed = {
  specialization: string | null;
  grade: string | null;
  grade_source: string | null;
  stack_must: string[];
  stack_nice: string[];
  work_format: string[];
  salary_from: number | null;
  salary_to: number | null;
  outside_specialization?: string[];
};

export type RubricPoint = { point: string; keywords: string[] };

export type RegularTask = {
  id: number;
  title: string;
  body: string;
  kind: "solve" | "approach";
  specialization: string;
  grades: string[];
  rubric: RubricPoint[];
  active: boolean;
  created_at: string;
  assigned?: number;
  submitted?: number;
  avg_auto_score?: number | null;
};
