/**
 * TypeScript mirror of backend/app/schemas.py (the API data contract).
 * Money is INR rupees (number). Rates are fractions (0.085 = 8.5%).
 * Dates/datetimes arrive as ISO strings.
 */

export type Product = "HOME_LOAN" | "LAP";
export type EmploymentType = "SALARIED" | "SELF_EMPLOYED";
export type DocType =
  | "PAN"
  | "AADHAAR"
  | "SALARY_SLIP"
  | "FORM16"
  | "ITR"
  | "BANK_STATEMENT"
  | "SALE_DEED"
  | "VALUATION_REPORT"
  | "UNKNOWN";
export type Severity = "INFO" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type RuleOutcome = "PASS" | "WARN" | "FAIL" | "INFO";
export type RuleCategory =
  | "ELIGIBILITY"
  | "FRAUD"
  | "COMPLIANCE"
  | "KYC"
  | "DOCUMENT"
  | "BANKING"
  | "RISK"
  | "CAPACITY";
export type DecisionOutcome = "APPROVE" | "APPROVE_WITH_CONDITIONS" | "REFER" | "DECLINE";
export const DECISION_OUTCOMES: DecisionOutcome[] = ["APPROVE", "APPROVE_WITH_CONDITIONS", "REFER", "DECLINE"];
export type CaseStatus =
  | "PROCESSING"
  | "AWAITING_DOCUMENTS"
  | "DECIDED"
  | "IN_REVIEW"
  | "OVERRIDDEN"
  | "SANCTIONED";
export type RuleEffect = "NONE" | "CONDITION" | "REFER" | "DECLINE" | "REDUCE_AMOUNT";
export type Grade = "A" | "B" | "C" | "D" | "E";

/** JSON value as returned by `Any` fields. */
export type Json = string | number | boolean | null | Json[] | { [key: string]: Json };
export type JsonObject = { [key: string]: Json };

export interface CoApplicant {
  name: string;
  relation: string;
  monthly_net_income: number;
  existing_emi: number;
}

export interface ApplicationForm {
  product: Product;
  applicant_name: string;
  dob?: string | null;
  gender?: "M" | "F" | "O" | null;
  mobile_masked?: string | null;
  city?: string | null;
  employment_type: EmploymentType;
  employer_or_business?: string | null;
  years_in_job: number;
  declared_monthly_income: number;
  existing_emi: number;
  bureau_score?: number | null;
  loan_amount: number;
  tenure_months: number;
  property_value: number;
  property_type: "RESIDENTIAL" | "COMMERCIAL" | "PLOT";
  property_city?: string | null;
  purpose: string;
  lap_end_use?: string | null;
  co_applicant?: CoApplicant | null;
  is_first_home: boolean;
  rate_type: "FLOATING" | "FIXED";
}

export interface Transaction {
  date: string;
  description: string;
  amount: number;
  balance?: number | null;
  category?: string | null;
}

export interface ExtractedField {
  name: string;
  value: Json;
  confidence: number;
  source: string;
}

export interface Flag {
  code: string;
  title: string;
  detail: string;
  severity: Severity;
  document_id?: string | null;
  evidence: JsonObject;
}

export interface DocumentResult {
  id: string;
  filename: string;
  doc_type: DocType;
  mime_type: string;
  pages: number;
  ocr_engine: string;
  classification_confidence: number;
  fields: ExtractedField[];
  flags: Flag[];
  text_excerpt: string;
  sha256: string;
  metadata: JsonObject;
}

export interface CrossCheck {
  field: string;
  values: JsonObject;
  match: boolean;
  score: number;
  note: string;
}

export interface DocumentBundle {
  documents: DocumentResult[];
  transactions: Transaction[];
  salary_slips: JsonObject[];
  identity: JsonObject;
  income_docs: JsonObject;
  property: JsonObject;
  cross_checks: CrossCheck[];
  flags: Flag[];
  missing_documents: DocType[];
}

export interface MonthlyBank {
  month: string;
  credits: number;
  debits: number;
  net?: number;
  closing?: number;
  avg_balance?: number;
  txn_count?: number;
}

export interface BankAnalytics {
  months_covered: number;
  avg_monthly_balance: number;
  min_balance: number;
  avg_monthly_credits: number;
  avg_monthly_debits: number;
  salary_credits: JsonObject[];
  avg_salary_credit: number;
  salary_regularity: number;
  detected_emis: JsonObject[];
  total_detected_emi: number;
  bounces: number;
  bounce_details: JsonObject[];
  cash_deposit_spikes: JsonObject[];
  high_risk_merchants: JsonObject[];
  monthly: MonthlyBank[];
  income_estimate: number;
  notes: string[];
  total_credits: number;
  total_debits: number;
  cash_deposit_total: number;
  cash_deposit_share: number;
  high_risk_debit_share: number;
  round_number_share: number;
  duplicate_txn_share: number;
  latest_balance: number;
  avg_monthly_rent?: number;
}

export interface TenureOption {
  tenure_months: number;
  max_loan: number;
  emi_for_requested: number;
  foir_at_requested: number;
}

export interface Eligibility {
  policy_version: string;
  assessed_income: number;
  income_basis: string;
  existing_obligations: number;
  foir_cap: number;
  foir_actual: number;
  ltv_cap: number;
  ltv_actual: number;
  ltv_rule_id: string;
  rate: number;
  max_tenure_months: number;
  age_at_maturity: number;
  max_emi_affordable: number;
  max_loan_by_foir: number;
  max_loan_by_ltv: number;
  max_eligible_loan: number;
  requested_amount: number;
  requested_emi: number;
  eligible: boolean;
  tenure_options: TenureOption[];
  notes: string[];
  tenure_months: number;
  property_value: number;
}

export interface ShapReason {
  feature: string;
  label: string;
  value: Json;
  impact: number;
  text: string;
}

export interface RiskScore {
  pd: number;
  score: number;
  grade: Grade;
  band: string;
  reasons: ShapReason[];
  base_value: number;
  model_version: string;
  features: JsonObject;
}

export interface ForecastPoint {
  month: number;
  p10: number;
  p50: number;
  p90: number;
}

export interface SubScore {
  name: string;
  score: number;
  weight: number;
  detail: string;
}

export interface RepaymentCapacity {
  health_score: number;
  sub_scores: SubScore[];
  monthly_surplus_after_emi: number;
  forecast: ForecastPoint[];
  prob_shortfall: number;
  stress_emi_coverage: number;
  iterations: number;
  basis: string;
}

export interface RuleHit {
  rule_id: string;
  name: string;
  category: RuleCategory;
  outcome: RuleOutcome;
  detail: string;
  effect: RuleEffect;
  severity: Severity;
  reference?: string | null;
  evidence: JsonObject;
}

export interface Condition {
  code: string;
  text: string;
  params: JsonObject;
}

export interface Decision {
  outcome: DecisionOutcome;
  engine_outcome: DecisionOutcome;
  model_suggested: DecisionOutcome;
  sanctioned_amount: number;
  tenure_months: number;
  rate: number;
  emi: number;
  reasons: string[];
  conditions: Condition[];
  rules_fired: RuleHit[];
  decided_by: string;
  decided_at: string;
  turnaround_ms: number;
  policy_version: string;
}

export interface Override {
  at: string;
  underwriter: string;
  from_outcome: DecisionOutcome;
  to_outcome: DecisionOutcome;
  reason: string;
  sanctioned_amount?: number | null;
}

export interface AuditEvent {
  at: string;
  actor: string;
  action: string;
  detail: string;
  data: JsonObject;
  hash: string;
}

export interface ApplicantProfile {
  name: string;
  dob?: string | null;
  age: number;
  gender?: string | null;
  pan_masked?: string | null;
  aadhaar_masked?: string | null;
  address?: string | null;
  city?: string | null;
  employment_type: EmploymentType;
  employer_or_business?: string | null;
}

export interface CaseSummary {
  id: string;
  applicant_name: string;
  product: Product;
  loan_amount: number;
  property_value: number;
  status: CaseStatus;
  outcome?: DecisionOutcome | null;
  pd?: number | null;
  grade?: string | null;
  flags: number;
  created_at: string;
  turnaround_ms: number;
  persona_id?: string | null;
  segment?: string | null;
}

export interface TraceStep {
  node: string;
  ms: number;
  summary: string;
  status: string;
}

export interface CaseDetail {
  id: string;
  persona_id?: string | null;
  created_at: string;
  status: CaseStatus;
  form: ApplicationForm;
  applicant: ApplicantProfile;
  bundle: DocumentBundle;
  bank: BankAnalytics;
  eligibility: Eligibility;
  risk: RiskScore;
  capacity: RepaymentCapacity;
  decision: Decision;
  overrides: Override[];
  audit: AuditEvent[];
  memo_markdown: string;
  copilot_trace: TraceStep[];
  disclaimer: string;
}

export interface OverrideRequest {
  underwriter: string;
  to_outcome: DecisionOutcome;
  reason: string;
  sanctioned_amount?: number | null;
}

export interface CopilotRequest {
  question: string;
}

export interface Citation {
  kind: "rule" | "policy" | "document" | "metric";
  ref: string;
  text: string;
}

export interface CopilotAnswer {
  answer: string;
  citations: Citation[];
  engine: string;
  grounded: boolean;
}

export interface TopRule {
  rule_id: string;
  name: string;
  category: string;
  count: number;
}

export interface PortfolioMetrics {
  total_cases: number;
  by_outcome: Record<string, number>;
  by_product: Record<string, number>;
  approval_rate: number;
  avg_turnaround_ms: number;
  fraud_flagged: number;
  avg_pd: number;
  sanctioned_value: number;
  override_rate: number;
  grade_distribution: Record<string, number>;
  top_rules: TopRule[];
}

/* ---------- API-only response models (backend/app/api/routes.py) ---------- */

export interface PersonaInfo {
  id: string;
  applicant_name: string;
  product: string;
  employment_type: string;
  city?: string | null;
  loan_amount: number;
  property_value: number;
  title?: string | null;
  segment?: string | null;
  description?: string | null;
  expected_outcomes: string[];
  files: string[];
  case_id?: string | null;
}

export interface PersonaDetail extends PersonaInfo {
  form: ApplicationForm;
  expected: JsonObject;
}

export interface HealthResponse {
  status: string;
  version: string;
  policy_version?: string | null;
  demo_mode: boolean;
  cases: number;
  preload: JsonObject;
  llm: JsonObject;
  modules: Record<string, boolean>;
  uptime_s: number;
}

export interface PolicyDoc {
  version: string;
  policy: JsonObject;
  rules: Record<string, JsonObject>;
}

/** /model-card is a free-form dict; the fields the UI reads are typed loosely. */
export type ModelCard = JsonObject;

export interface DemoResetResponse {
  cases: number;
  errors: JsonObject[];
  ms: number;
}

/** Static snapshot used in demo mode (written by scripts/export_snapshot.mjs). */
export interface DemoSnapshot {
  generated_at: string;
  cases: CaseDetail[];
  personas: PersonaInfo[];
  persona_details?: PersonaDetail[];
  portfolio: PortfolioMetrics;
  policy: PolicyDoc;
  model_card: ModelCard;
  memos?: Record<string, string>;
  letters?: Record<string, string>;
}
