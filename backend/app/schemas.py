"""Shared, typed contract for FinPilot HomeLoan.

Every module (documents, engine, ml, capacity, agent, api) exchanges these
Pydantic models. The frontend mirrors them in `frontend/src/lib/types.ts`.
Monetary values are INR (float, rupees). Rates are fractions (0.085 = 8.5%).
PII rule: full PAN/Aadhaar numbers never leave the documents layer; only
masked forms (`XXXXXXXX1234`, `XXXXXX1234F`) are stored in these models.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- enums
class Product(str, Enum):
    HOME_LOAN = "HOME_LOAN"
    LAP = "LAP"  # Loan Against Property


class EmploymentType(str, Enum):
    SALARIED = "SALARIED"
    SELF_EMPLOYED = "SELF_EMPLOYED"  # professional / business


class DocType(str, Enum):
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    SALARY_SLIP = "SALARY_SLIP"
    FORM16 = "FORM16"
    ITR = "ITR"
    BANK_STATEMENT = "BANK_STATEMENT"
    SALE_DEED = "SALE_DEED"  # sale deed / agreement for sale / title deed (LAP)
    VALUATION_REPORT = "VALUATION_REPORT"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RuleOutcome(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    INFO = "INFO"


class RuleCategory(str, Enum):
    ELIGIBILITY = "ELIGIBILITY"
    FRAUD = "FRAUD"
    COMPLIANCE = "COMPLIANCE"
    KYC = "KYC"
    DOCUMENT = "DOCUMENT"
    BANKING = "BANKING"
    RISK = "RISK"
    CAPACITY = "CAPACITY"


class DecisionOutcome(str, Enum):
    APPROVE = "APPROVE"
    APPROVE_WITH_CONDITIONS = "APPROVE_WITH_CONDITIONS"
    REFER = "REFER"
    DECLINE = "DECLINE"


class CaseStatus(str, Enum):
    PROCESSING = "PROCESSING"
    AWAITING_DOCUMENTS = "AWAITING_DOCUMENTS"
    DECIDED = "DECIDED"          # engine decided (approve / conditions / decline)
    IN_REVIEW = "IN_REVIEW"      # referred to underwriter
    OVERRIDDEN = "OVERRIDDEN"    # human override applied
    SANCTIONED = "SANCTIONED"


# --------------------------------------------------------------------------- application inputs
class CoApplicant(BaseModel):
    name: str
    relation: str = "Spouse"
    monthly_net_income: float = 0.0
    existing_emi: float = 0.0


class ApplicationForm(BaseModel):
    """What the RM / applicant declares at intake (before documents are read)."""
    product: Product = Product.HOME_LOAN
    applicant_name: str
    dob: Optional[date] = None
    gender: Optional[Literal["M", "F", "O"]] = None
    mobile_masked: Optional[str] = None
    city: Optional[str] = None
    employment_type: EmploymentType = EmploymentType.SALARIED
    employer_or_business: Optional[str] = None
    years_in_job: float = 3.0
    declared_monthly_income: float  # net take-home (salaried) or avg monthly net (SE)
    existing_emi: float = 0.0
    bureau_score: Optional[int] = None  # CIBIL-like score from bureau pull (synthetic)
    loan_amount: float
    tenure_months: int = 240
    property_value: float
    property_type: Literal["RESIDENTIAL", "COMMERCIAL", "PLOT"] = "RESIDENTIAL"
    property_city: Optional[str] = None
    purpose: str = "Purchase of residential flat"
    lap_end_use: Optional[str] = None  # LAP only: business expansion, education, ...
    co_applicant: Optional[CoApplicant] = None
    is_first_home: bool = True
    rate_type: Literal["FLOATING", "FIXED"] = "FLOATING"


# --------------------------------------------------------------------------- documents
class Transaction(BaseModel):
    date: date
    description: str
    amount: float  # +credit / -debit
    balance: Optional[float] = None
    category: Optional[str] = None  # SALARY, EMI, CASH_DEPOSIT, BOUNCE, GAMBLING, ...


class ExtractedField(BaseModel):
    name: str            # e.g. "name", "dob", "net_pay", "employer", "pan_masked"
    value: Any
    confidence: float = 1.0
    source: str = "text"  # "text" (pdf text layer) | "ocr" | "derived"


class Flag(BaseModel):
    code: str            # e.g. "DOC_FONT_ANOMALY", "INCOME_INFLATION"
    title: str
    detail: str
    severity: Severity = Severity.MEDIUM
    document_id: Optional[str] = None
    evidence: dict[str, Any] = Field(default_factory=dict)


class DocumentResult(BaseModel):
    id: str
    filename: str
    doc_type: DocType
    mime_type: str = "application/pdf"
    pages: int = 1
    ocr_engine: str = "pdf-text"  # "pdf-text" | "rapidocr(paddle)" | "doctr" | "none"
    classification_confidence: float = 1.0
    fields: list[ExtractedField] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)
    text_excerpt: str = ""     # first ~600 chars, PII-masked
    sha256: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)  # pdf producer/creator/dates

    def field(self, name: str, default: Any = None) -> Any:
        for f in self.fields:
            if f.name == name:
                return f.value
        return default


class CrossCheck(BaseModel):
    field: str                      # "name", "dob", "address", "employer", "salary_vs_credit"
    values: dict[str, Any]          # doc_type/doc_id -> value seen
    match: bool
    score: float = 1.0              # similarity 0..1
    note: str = ""


class DocumentBundle(BaseModel):
    """Output of the document layer for one case."""
    documents: list[DocumentResult] = Field(default_factory=list)
    transactions: list[Transaction] = Field(default_factory=list)
    salary_slips: list[dict[str, Any]] = Field(default_factory=list)  # {month, gross, net, employer}
    identity: dict[str, Any] = Field(default_factory=dict)   # name, dob, pan_masked, aadhaar_masked, address
    income_docs: dict[str, Any] = Field(default_factory=dict)  # form16/itr: annual_income, employer, ay
    property: dict[str, Any] = Field(default_factory=dict)   # address, market_value, distress_value, area_sqft, owner, registration_no, encumbrance
    cross_checks: list[CrossCheck] = Field(default_factory=list)
    flags: list[Flag] = Field(default_factory=list)          # forgery / tampering / consistency flags
    missing_documents: list[DocType] = Field(default_factory=list)


# --------------------------------------------------------------------------- analytics
class BankAnalytics(BaseModel):
    months_covered: float = 0
    avg_monthly_balance: float = 0
    min_balance: float = 0
    avg_monthly_credits: float = 0
    avg_monthly_debits: float = 0
    salary_credits: list[dict[str, Any]] = Field(default_factory=list)  # {month, amount, date}
    avg_salary_credit: float = 0
    salary_regularity: float = 0     # 0..1 share of months with salary credit, low variance
    detected_emis: list[dict[str, Any]] = Field(default_factory=list)  # {lender, amount, months}
    total_detected_emi: float = 0
    bounces: int = 0
    bounce_details: list[dict[str, Any]] = Field(default_factory=list)
    cash_deposit_spikes: list[dict[str, Any]] = Field(default_factory=list)
    high_risk_merchants: list[dict[str, Any]] = Field(default_factory=list)  # gambling/crypto/betting
    monthly: list[dict[str, Any]] = Field(default_factory=list)  # {month, credits, debits, closing, avg_balance}
    income_estimate: float = 0       # robust monthly income estimate from credits
    notes: list[str] = Field(default_factory=list)
    # added by engine (optional, backwards compatible)
    total_credits: float = 0
    total_debits: float = 0
    cash_deposit_total: float = 0
    cash_deposit_share: float = 0     # cash deposits / total credits
    high_risk_debit_share: float = 0  # high-risk merchant debits / total debits
    round_number_share: float = 0     # share of txns that are exact multiples of Rs 1,000
    duplicate_txn_share: float = 0    # share of txns repeated verbatim (date, desc, amount, balance)
    latest_balance: float = 0


class TenureOption(BaseModel):
    tenure_months: int
    max_loan: float
    emi_for_requested: float
    foir_at_requested: float


class Eligibility(BaseModel):
    policy_version: str
    assessed_income: float            # monthly income used for FOIR (incl. co-applicant)
    income_basis: str                 # e.g. "min(declared, slips, bank salary credits)"
    existing_obligations: float
    foir_cap: float
    foir_actual: float                # (existing + proposed EMI) / income
    ltv_cap: float
    ltv_actual: float
    ltv_rule_id: str
    rate: float                       # annual rate applied
    max_tenure_months: int            # min(policy max, age-at-maturity limit)
    age_at_maturity: float
    max_emi_affordable: float
    max_loan_by_foir: float
    max_loan_by_ltv: float
    max_eligible_loan: float
    requested_amount: float
    requested_emi: float
    eligible: bool
    tenure_options: list[TenureOption] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    # added by engine (optional)
    tenure_months: int = 0            # effective tenure = min(requested, max_tenure_months)
    property_value: float = 0         # LTV basis: lower of agreement value and valuation


class ShapReason(BaseModel):
    feature: str
    label: str                 # human label: "Fixed obligation to income ratio"
    value: Any                 # feature value in display form
    impact: float              # SHAP value (log-odds); + increases risk
    text: str                  # plain-language sentence


class RiskScore(BaseModel):
    pd: float                  # calibrated probability of default (12m-equivalent)
    score: int                 # 300..900 scorecard-like transform
    grade: Literal["A", "B", "C", "D", "E"]
    band: str                  # "Low", "Moderate", "Elevated", "High", "Very high"
    reasons: list[ShapReason] = Field(default_factory=list)
    base_value: float = 0.0
    model_version: str = "unavailable"
    features: dict[str, Any] = Field(default_factory=dict)


class ForecastPoint(BaseModel):
    month: int
    p10: float
    p50: float
    p90: float


class SubScore(BaseModel):
    name: str
    score: float
    weight: float
    detail: str


class RepaymentCapacity(BaseModel):
    """Re-uses FinPilot's 5-pillar health score + Monte Carlo cash-flow forecast."""
    health_score: float
    sub_scores: list[SubScore] = Field(default_factory=list)
    monthly_surplus_after_emi: float
    forecast: list[ForecastPoint] = Field(default_factory=list)  # cumulative buffer after EMI, 12-24 months
    prob_shortfall: float            # P(buffer < 0 at any month) from Monte Carlo
    stress_emi_coverage: float       # surplus / EMI under +200bps rate shock & -15% income
    iterations: int = 1000
    basis: str = ""


# --------------------------------------------------------------------------- decision
class RuleHit(BaseModel):
    rule_id: str               # e.g. "ELG-FOIR-01" (matches policy YAML)
    name: str
    category: RuleCategory
    outcome: RuleOutcome
    detail: str
    effect: Literal["NONE", "CONDITION", "REFER", "DECLINE", "REDUCE_AMOUNT"] = "NONE"
    severity: Severity = Severity.INFO
    reference: Optional[str] = None   # regulatory citation, e.g. "RBI Master Circular DOR.CRE.REC.No.06/08.12.001/2023-24 para 2.3.1"
    evidence: dict[str, Any] = Field(default_factory=dict)


class Condition(BaseModel):
    code: str                  # "ADD_CO_APPLICANT", "REDUCE_AMOUNT", "INCREASE_TENURE", "SUBMIT_DOC", ...
    text: str
    params: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    outcome: DecisionOutcome
    engine_outcome: DecisionOutcome          # what the engine said before any override
    model_suggested: DecisionOutcome         # what ML alone (PD bands) would say
    sanctioned_amount: float = 0
    tenure_months: int = 0
    rate: float = 0
    emi: float = 0
    reasons: list[str] = Field(default_factory=list)      # top plain-language reasons
    conditions: list[Condition] = Field(default_factory=list)
    rules_fired: list[RuleHit] = Field(default_factory=list)
    decided_by: str = "engine"               # "engine" | underwriter name
    decided_at: datetime
    turnaround_ms: int = 0
    policy_version: str = ""


class Override(BaseModel):
    at: datetime
    underwriter: str
    from_outcome: DecisionOutcome
    to_outcome: DecisionOutcome
    reason: str
    sanctioned_amount: Optional[float] = None


class AuditEvent(BaseModel):
    at: datetime
    actor: str          # "system", "copilot", "ml-model", "underwriter:<name>"
    action: str         # "DOCUMENT_INGESTED", "RULE_FIRED", "MODEL_SCORED", "DECISION", "OVERRIDE", ...
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)
    hash: str = ""      # sha256 chain: hash(prev_hash + this event json)


class ApplicantProfile(BaseModel):
    name: str
    dob: Optional[date] = None
    age: float = 0
    gender: Optional[str] = None
    pan_masked: Optional[str] = None
    aadhaar_masked: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    employment_type: EmploymentType
    employer_or_business: Optional[str] = None


class CaseSummary(BaseModel):
    id: str
    applicant_name: str
    product: Product
    loan_amount: float
    property_value: float
    status: CaseStatus
    outcome: Optional[DecisionOutcome] = None
    pd: Optional[float] = None
    grade: Optional[str] = None
    flags: int = 0
    created_at: datetime
    turnaround_ms: int = 0
    persona_id: Optional[str] = None
    segment: Optional[str] = None


class CaseDetail(BaseModel):
    id: str
    persona_id: Optional[str] = None
    created_at: datetime
    status: CaseStatus
    form: ApplicationForm
    applicant: ApplicantProfile
    bundle: DocumentBundle
    bank: BankAnalytics
    eligibility: Eligibility
    risk: RiskScore
    capacity: RepaymentCapacity
    decision: Decision
    overrides: list[Override] = Field(default_factory=list)
    audit: list[AuditEvent] = Field(default_factory=list)
    memo_markdown: str = ""
    copilot_trace: list[dict[str, Any]] = Field(default_factory=list)  # LangGraph node trace
    disclaimer: str = (
        "Decision support for underwriters. Final credit decisions follow the lender's "
        "board-approved credit policy and applicable RBI/NHB regulations."
    )

    def summary(self) -> CaseSummary:
        flags = len(self.bundle.flags) + sum(
            1 for r in self.decision.rules_fired
            if r.category in (RuleCategory.FRAUD,) and r.outcome == RuleOutcome.FAIL
        )
        return CaseSummary(
            id=self.id, applicant_name=self.applicant.name, product=self.form.product,
            loan_amount=self.form.loan_amount, property_value=self.form.property_value,
            status=self.status, outcome=self.decision.outcome, pd=self.risk.pd,
            grade=self.risk.grade, flags=flags, created_at=self.created_at,
            turnaround_ms=self.decision.turnaround_ms, persona_id=self.persona_id,
        )


# --------------------------------------------------------------------------- api payloads
class OverrideRequest(BaseModel):
    underwriter: str
    to_outcome: DecisionOutcome
    reason: str = Field(min_length=5)
    sanctioned_amount: Optional[float] = None


class CopilotRequest(BaseModel):
    question: str


class Citation(BaseModel):
    kind: Literal["rule", "policy", "document", "metric"]
    ref: str          # rule_id / policy key / document id / metric name
    text: str


class CopilotAnswer(BaseModel):
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    engine: str = "grounded-template"   # "ollama:<model>" | "gemini:<model>" | "grounded-template"
    grounded: bool = True


class PortfolioMetrics(BaseModel):
    total_cases: int
    by_outcome: dict[str, int]
    by_product: dict[str, int]
    approval_rate: float
    avg_turnaround_ms: float
    fraud_flagged: int
    avg_pd: float
    sanctioned_value: float
    override_rate: float
    grade_distribution: dict[str, int]
    top_rules: list[dict[str, Any]]
