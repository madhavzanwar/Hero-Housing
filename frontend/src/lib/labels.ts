import type { CaseStatus, DecisionOutcome, DocType, RuleOutcome, Severity } from "./types";

export const OUTCOME_LABEL: Record<DecisionOutcome, string> = {
  APPROVE: "Approved",
  APPROVE_WITH_CONDITIONS: "Approved with conditions",
  REFER: "Refer to underwriter",
  DECLINE: "Declined",
};

export const OUTCOME_SHORT: Record<DecisionOutcome, string> = {
  APPROVE: "Approve",
  APPROVE_WITH_CONDITIONS: "With conditions",
  REFER: "Refer",
  DECLINE: "Decline",
};

export const STATUS_LABEL: Record<CaseStatus, string> = {
  PROCESSING: "Processing",
  AWAITING_DOCUMENTS: "Awaiting documents",
  DECIDED: "Decided",
  IN_REVIEW: "In review",
  OVERRIDDEN: "Overridden",
  SANCTIONED: "Sanctioned",
};

export const DOC_LABEL: Record<DocType, string> = {
  PAN: "PAN card",
  AADHAAR: "Aadhaar",
  SALARY_SLIP: "Salary slip",
  FORM16: "Form 16",
  ITR: "ITR",
  BANK_STATEMENT: "Bank statement",
  SALE_DEED: "Sale deed / agreement",
  VALUATION_REPORT: "Valuation report",
  UNKNOWN: "Unclassified",
};

export const SEVERITY_LABEL: Record<Severity, string> = {
  INFO: "Info",
  LOW: "Low",
  MEDIUM: "Medium",
  HIGH: "High",
  CRITICAL: "Critical",
};

export const RULE_OUTCOME_LABEL: Record<RuleOutcome, string> = {
  PASS: "Pass",
  WARN: "Warn",
  FAIL: "Fail",
  INFO: "Info",
};

export const NODE_LABEL: Record<string, string> = {
  intake: "Intake",
  documents: "Document AI",
  missing_docs_check: "Missing-docs check",
  bank_analytics: "Bank analytics",
  eligibility: "Eligibility engine",
  fraud_compliance: "Fraud & compliance",
  risk_model: "Risk model + SHAP",
  capacity: "Repayment capacity",
  decision: "Decision",
  credit_memo: "Credit memo",
  audit: "Audit seal",
};

export const PIPELINE_NODES = Object.keys(NODE_LABEL);
