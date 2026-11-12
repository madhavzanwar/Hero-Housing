# Submission — Hero Housing Fintech Challenge (E-Cell IIT Bombay × Hero Housing Finance)

**Team:** DoubleStack — Madhav Zanwar, Divyani Papalkar (PCCoE, Pune)
**Problem statement:** PS2 — Digitally Automated Mortgage Underwriting Engine (Home Loans & LAP)

## Title
**FinPilot HomeLoan — explainable mortgage underwriting in minutes**

## One-line pitch
Upload an applicant's documents and get an RBI-aligned, fully explained Approve / Approve-with-conditions / Refer / Decline decision with a sanction-ready memo in under 3 seconds. Every number is traced to a document, a rule ID or a model reason, and the underwriter can override anything.

## Abstract (≈300 words)
Home-loan underwriting in India still takes days. Teams re-key PAN, Aadhaar, salary slips, ITRs, 6–12 months of bank statements and property papers, apply FOIR/LTV policy by hand, and catch forged slips or inflated income only by chance. FinPilot HomeLoan automates that journey for Home Loans and Loans Against Property while keeping a human in control.

A LangGraph "Underwriting Copilot" runs the case through nine nodes:
- **Document intelligence:** PDF text-layer parsing plus PaddleOCR-ONNX for scans. Aadhaar and PAN are masked at the point of ingestion.
- **Cross-document checks:** name, DOB, address, employer, and salary slip against bank credit.
- **Tampering heuristics:** PDF producer and edit metadata, font anomalies, round-number patterns, and duplicate statements.
- **Bank-statement analytics:** average balance, salary regularity, detected EMIs, bounces, cash spikes, and gambling or crypto spends.
- **Eligibility:** FOIR caps by income band, LTV slabs per RBI HFC Directions 2025 para 58 (90/80/75%), age at maturity, and LAP end-use and LTV rules. All thresholds sit in a versioned YAML policy file.
- **Fraud and compliance:** a negative/PEP list, income-inflation detection, KYC completeness and a CERSAI placeholder.
- **Risk score:** a calibrated LightGBM PD with plain-language SHAP reasons and a fairlearn fairness audit.
- **Repayment capacity:** a 1,000-path Monte Carlo cash-flow stress test reused from our FinPilot project.
- **Decision:** a rules-plus-ML hybrid in which policy rules always dominate.

The decision card lists the top reasons and concrete conditions ("reduce to ₹27.9 L", "add a co-applicant earning ₹38,000/month", "increase tenure to 300 months"). It also shows the sanction amount and EMI and every rule fired, each with its regulatory citation. Underwriters review documents next to the extracted fields, override with a recorded reason, and question the Copilot. Its answers are grounded only in case data and policy and cite rule IDs. It runs on a local Ollama model, optionally Gemini, or a deterministic grounded engine with no paid key at all. A hash-chained audit trail, a credit memo and a sanction-letter draft with a KFS-style summary complete the file.

Across 12 synthetic Indian personas, including a forged-salary-slip fraud and a borderline refer, decisions arrive in seconds, against days today. This is decision support: final credit decisions follow the lender's policy.

## Links
- **Live demo:** _LIVE_URL_
- **Repository:** _REPO_URL_ (placeholder — e.g. https://github.com/madhavzanwar/Hero-Housing)
- **Demo video:** `submission/demo.mp4`
- **Deck:** `submission/deck.pptx`

## Files to upload
| File | What |
|---|---|
| `submission/deck.pptx` | 12-slide pitch deck |
| `submission/demo.mp4` | ≤ 3-minute walkthrough with voiceover and subtitles |
| `SUBMISSION.md` | this page (title, pitch, abstract, links) |
| Repository link | full source, README, MODEL_CARD, QA report |
