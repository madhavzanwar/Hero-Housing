"""Deck content. External facts carry a [n] tag that maps to SOURCES (Appendix A).
Prototype numbers come from this repository (synthetic data) and are labelled as such.
Targets are labelled TARGET with assumptions — never presented as achieved results.
"""
from __future__ import annotations

# ----------------------------------------------------------------------------- problem
PROBLEM_LEAD = ("Hero Housing lends Home Loans and LAP to mid- and affordable-segment retail borrowers across 11 states. "
                "The book is growing and still young — underwriting has to scale without loosening credit or compliance [1].")

# (big number, explanation, source tag) — all verified in research/NOTES.md
PROBLEM_FACTS: list[tuple[str, str, str]] = [
    ("₹7,160 Cr", "AUM, Dec-2025: Home Loans 56%, LAP 35% — both products PS2 targets", "ICRA rating rationale, Mar-2026 [1]"),
    ("1.7% → 2.4%", "Gross stage 3 rose in nine months on a young, unseasoned book", "ICRA rating rationale, Mar-2026 [1]"),
    ("₹31,911 Cr", "Bank frauds in advances, FY2024-25 (7,934 cases) — loan files are a fraud target", "RBI Trend & Progress of Banking [2]"),
    ("1-Oct-2024", "KFS mandatory for all new retail loans; written rejection reasons; DPDP Rules 2025", "RBI [4] [5], MeitY / PIB [11]"),
]

PAINS = [
    ("timer", "Slow, manual review", "Documents re-keyed and FOIR/LTV computed by hand while applicants wait."),
    ("wallet", "Hard-to-read income", "Self-employed and cash-heavy incomes need bank-flow and GST analytics, not just ITRs."),
    ("triangle-alert", "Fraud in paperwork", "Edited slips, inflated income and properties pledged twice slip through."),
    ("scale", "Explain every decision", "Written reasons, KFS and audit trails — and now AI governance too."),
]

SOLUTION_FOOT = ("A rules + ML hybrid: the versioned policy engine always has the last word, the calibrated model sets risk "
                 "grade and price, and every step writes to a hash-chained audit ledger. Clean files go straight through; "
                 "only exceptions reach a person.")

# ----------------------------------------------------------------------------- the 8 required points
POINTS = [
    {
        "n": 1, "title": "1 · Integrate data sources",
        "what": "Consent-first connectors fetch bank, bureau, KYC, income and property data in parallel — no re-keying.",
        "flow": ["Consent\nDPDP notice + AA artefact", "Parallel fetch\n8+ connectors", "Normalise & mask\nPII minimised",
                 "Case evidence\nversioned, hashed"],
        "highlight": 0,
        "detail": [
            ('link-2', 'AA first', 'Signed bank data; PDFs only as fallback'),
            ('refresh-ccw', 'Resilient', 'Timeouts, retries; gaps refer, never guess'),
            ('eye', 'Visible', 'Status and consent id per source'),
        ],
        "data": ["Account Aggregator", "Credit bureau", "NSDL PAN", "Aadhaar offline e-KYC", "CKYCR", "AIS / Form 26AS",
                 "GSTN", "ITR", "CERSAI", "Land records / IGR", "Circle rates", "UN sanctions list"],
        "callout": ("Regulatory fit", 'AA network: 595 M consents fulfilled by Sep-2026 [9]. Prior, purpose-specific consent [8] [11]; Aadhaar masked to last 4 digits [6] [12].'),
        "notes": ("Point one is data. We are AA-first: bank statements arrive as signed financial-information data through "
                  "the Account Aggregator network, with the borrower's consent artefact recorded on the case. In parallel we "
                  "call the bureau, PAN verification, Aadhaar offline e-KYC, CKYC, income sources like 26AS and GST, and the "
                  "property side — CERSAI, land records and circle rates — plus sanctions lists. Everything lands in one "
                  "versioned, hashed evidence store, with PII masked at the door. If a source is down, we don't guess: the "
                  "case is referred with that gap visible."),
    },
    {
        "n": 2, "title": "2 · Eligibility & policy",
        "what": "Real-time Home Loan and LAP eligibility from a versioned policy file; every threshold has a rule ID.",
        "flow": ["Assess income\nmin(declared, slips, bank)", "FOIR cap\nby income band", "LTV cap\nby loan slab",
                 "Max eligible loan\n& tenure options"],
        "highlight": 3,
        "detail": [
            ('banknote', 'Informal income', 'Bank-flow and GST analytics for self-employed'),
            ('clipboard-list', 'Policy as code', '45 rules in versioned YAML'),
            ('split', 'Deviations', 'Routed to the delegation matrix, gap quantified'),
        ],
        "data": ["Salary slips", "Form 16 / ITR", "Bank analytics", "Bureau EMIs", "Property value", "Applicant age"],
        "callout": ("Regulatory fit", 'LTV caps, HFC Directions 2025 para 58: ≤ ₹30 L 90%, ₹30–75 L 80%, > ₹75 L 75%, excluding stamp duty [3]. LAP caps are internal policy.'),
        "notes": ("Point two, eligibility and policy. Income is assessed conservatively: the minimum of what's declared, what "
                  "the slips show and what actually lands in the bank. For self-employed borrowers we read business cash flows and GST patterns, not just the ITR. FOIR caps vary by "
                  "income band; LTV follows the RBI HFC Directions 2025 slabs; tenure respects age at maturity. All of it "
                  "lives in one versioned YAML policy with rule IDs, so credit policy can change a threshold without "
                  "touching code, and every decision records which policy version it used."),
    },
    {
        "n": 3, "title": "3 · Fraud detection & KYC/AML",
        "what": "Automated forensics, identity and AML checks replace manual review; only real exceptions are referred.",
        "flow": ["Document forensics\nmetadata · fonts · math", "Cross-checks\nname · DOB · employer",
                 "Fraud graph\nshared phone · address", "KYC & AML\nPAN · CKYC · sanctions"],
        "highlight": 2,
        "detail": [
            ('scan-search', 'Tamper detection', 'Editor metadata, font changes, reused templates'),
            ('network', 'Fraud graph', 'Shared phones, addresses, employers, devices'),
            ('search-check', 'Screening', 'UN list (UAPA s.51A), PEP, STR drafts'),
        ],
        "data": ["Uploaded documents", "PDF metadata", "Bank transactions", "NSDL PAN", "CKYCR", "UN sanctions list",
                 "PEP / internal lists", "Device signals"],
        "callout": ("Regulatory fit", 'KYC Directions 2025 [6]: V-CIP (para 27), CKYCR in 10 days (para 63), UNSC screening (para 54), STR/CTR to FIU-IND [7].'),
        "callout_icon": "shield-check",
        "notes": ("Point three. A lot of loan fraud starts in the paperwork: edited salary slips, inflated income, "
                  "re-used templates. Our document AI checks PDF metadata — for example a slip produced by an online PDF "
                  "editor — font changes on the figures, and arithmetic. It cross-checks name, date of birth, employer and "
                  "salary against bank credits. A linked-entity graph catches rings sharing phones, addresses or devices. "
                  "Identity runs through PAN, offline e-KYC and CKYC; AML screens against the UN list and PEP lists. In our "
                  "prototype, the forged-slip persona is declined in under a second, with written reasons."),
    },
    {
        "n": 4, "title": "4 · Risk scoring",
        "what": "Every application gets a calibrated PD, a 300–900 score, a grade and plain-English reasons.",
        "flow": ["18 features\nFOIR · LTV · bank · bureau", "Gradient boosting\nmonotone constraints", "Calibration\nPD that means PD",
                 "Grade A–E\n+ SHAP reason codes"],
        "highlight": 3,
        "detail": [
            ('chart-line', 'Prototype (synthetic, n = 12,000)', 'AUC 0.83 · KS 0.53 · well calibrated'),
            ('book-open-check', 'Public benchmark', 'UCI credit default: AUC 0.78 [16]'),
            ('users', 'Fairness', 'Gender approval gap 1.1 pp; not a feature'),
        ],
        "data": ["Bureau score", "FOIR", "LTV", "Bounces", "Balance vs EMI", "Income regularity", "Cash share", "Tenure"],
        "callout": ("Explainability", 'Top-5 SHAP reasons per case. Monotone constraints: higher FOIR never lowers risk. The model prices risk; it never overrides policy.'),
        "callout_icon": "gauge",
        "notes": ("Point four. The score comes from a gradient-boosted model with monotone constraints — so the model can never "
                  "say that a higher FOIR or more bounces makes someone safer. It is calibrated, so a 5% PD really means about "
                  "five in a hundred. On our synthetic test set of twelve thousand files, AUC is 0.83 and calibration error is "
                  "under half a percentage point; on public credit-default data the same method scores 0.78. Every case shows "
                  "its top five reasons in plain English, and we audit fairness across gender and age bands."),
    },
    {
        "n": 5, "title": "5 · Documents & property",
        "what": "Documents verified digitally and the property assessed in the same flow — one decision, not two queues.",
        "flow": ["Document AI\nclassify · OCR · extract", "Verify\ncross-checks · mask PII", "Property\ntitle · CERSAI · AVM",
                 "LTV on\nconservative value"],
        "highlight": 2,
        "detail": [
            ('file-search', 'Document AI', 'Text layer + open-source OCR, field confidence'),
            ('house', 'Valuation', 'Comparables + circle rate → value range'),
            ('route', 'Routing', 'Low confidence or title issue → site visit'),
        ],
        "data": ["PAN / Aadhaar", "Salary slips", "Bank statements", "Sale deed / agreement", "Valuation report", "CERSAI",
                 "Land records", "Circle rates", "Comparables"],
        "callout": ("Regulatory fit", 'LTV on realisable value excluding stamp duty (para 58); Board-approved valuation policy (para 215) [3]; CERSAI search stops double-pledging [10].'),
        "callout_icon": "house",
        "notes": ("Point five. Documents are classified, read and cross-checked automatically — PDF text where it exists, "
                  "open-source OCR for scans, and every field carries a confidence. Aadhaar is masked at the moment we read it. "
                  "The property is assessed inside the same flow: title and encumbrance via CERSAI and land records, and an "
                  "automated valuation from comparables and circle rates that gives a range, not just a number. LTV is taken on "
                  "the conservative value, and the valuation's confidence decides whether a desk review is enough or a site "
                  "visit is needed."),
    },
    {
        "n": 6, "title": "6 · Compliance checks",
        "what": "Compliance is code: each obligation is a rule with an ID and citation that blocks, conditions or refers.",
        "flow": ["Regulation\ncited paragraph", "Rule in policy YAML\nID + effect", "Checked on every case\npass · warn · fail",
                 "Evidence in\naudit ledger"],
        "highlight": 1,
        "detail": [
            ('file-text', 'Fair Practices Code', 'Written rejection reasons (para 135) [3]'),
            ('receipt', 'Key Facts Statement', 'APR sheet + schedule, valid 3 days [5]'),
            ('landmark', 'NHB', 'Supervises HFCs (para 234); grievance route [3]'),
        ],
        "data": ["Policy YAML", "Rule catalogue", "Regulatory references", "Case evidence", "Audit ledger"],
        "callout": ("Audit standard", 'Every rule, score and override goes to a hash-chained ledger with policy and model versions; records kept ≥ 5 years [6].'),
        "callout_icon": "book-open-check",
        "notes": ("Point six. Instead of a compliance checklist at the end, compliance is inside the engine. Each obligation — "
                  "LTV caps, KYC, the Fair Practices Code, the Key Facts Statement — is a rule with an ID, an effect and the "
                  "paragraph it comes from. A rejection automatically produces a letter with written reasons; an approval "
                  "produces a KFS with the annual percentage rate. Every rule result goes into the hash-chained ledger, so an "
                  "auditor or NHB inspector can see exactly why each decision was made."),
    },
    {
        "n": 7, "title": "7 · Instant decisioning",
        "what": "A humanless decision in seconds — approve, reject or refer — with conditions that show the path to yes.",
        "flow": ["Hard-rule fail\n→ reject", "Exception\n→ refer", "Fixable gap\n→ conditions", "All clear\n→ approve"],
        "highlight": 3,
        "detail": [
            ('zap', 'Prototype', '12/12 synthetic personas, 0.3–2 s each'),
            ('coins', 'Path to yes', '“Reduce to ₹37.1 L or add a co-applicant”'),
            ('bell-ring', 'Refer queues', 'Credit, fraud, KYC, legal — with SLA'),
        ],
        "data": ["Eligibility", "Fraud & KYC results", "PD & grade", "Capacity stress test", "Property route"],
        "callout": ("Explainability", 'Fixed precedence: policy decline > refer > conditions > approve. A model-only decline becomes a refer — no black-box rejections.'),
        "callout_icon": "circle-check-big",
        "notes": ("Point seven, instant decisioning. The order of precedence is fixed: a hard policy failure rejects, an "
                  "exception refers, a fixable gap becomes conditions, and a clean file is approved straight through — no "
                  "human needed. Conditions are concrete: in our prototype, a borrower with heavy existing EMIs gets 'reduce "
                  "to 37.1 lakh, or add a co-applicant earning 34,200 a month'. Across our twelve synthetic personas, decisions "
                  "take between a third of a second and two seconds, and all twelve match the expected outcome."),
    },
    {
        "n": 8, "title": "8 · Explainability & governance",
        "what": "Every decision is explainable, traceable and replayable — for borrower, underwriter and regulator.",
        "flow": ["Reason codes\nrule IDs + SHAP", "Versioned\npolicy & model hash", "Hash-chained\naudit ledger",
                 "Replay\nsame inputs → same hash"],
        "highlight": 3,
        "detail": [
            ('history', 'Overrides', 'Reason required; four eyes for fraud'),
            ('git-branch', 'Model risk', 'Challenger, drift and fairness monitoring'),
            ('sparkles', 'Copilot', 'Answers only from case data, cites rule IDs'),
        ],
        "data": ["Rule results", "SHAP values", "Policy hash", "Model version", "Overrides", "Copilot trace"],
        "callout": ("Regulatory fit", 'RBI FREE-AI (Aug-2025) [13]: humans keep final authority (Sutra 2), Board AI policy (Rec 14), model lifecycle (Rec 16), AI audit (Rec 24).'),
        "callout_icon": "history",
        "notes": ("Point eight. Every decision carries its reasons: the rule IDs that fired and the model's SHAP drivers. The "
                  "policy file and model are hashed and recorded on each decision, and the audit ledger is hash-chained, so "
                  "tampering is detectable. We can replay any decision from its stored inputs and prove we get the same "
                  "result. Overrides require a written reason, fraud overrides need four eyes, and a challenger model runs in "
                  "shadow for model-risk monitoring — in line with RBI's FREE-AI recommendations."),
    },
]

ARCH_FOOT = ("Stateless engines scale horizontally behind the orchestrator; documents encrypted at rest; India-region "
             "hosting for data residency; every engine call is traced and versioned.")

# ----------------------------------------------------------------------------- impact
KPIS = [
    ("< 10 min", "Login to decision", "Assumes AA consent and documents available at login; prototype decides in ≤ 2 s"),
    ("50–70%", "Straight-through rate", "Assumes clean salaried Home Loan files are the majority; tune after pilot"),
    ("~60%", "Less manual effort / file", "Assumes re-keying and FOIR/LTV calculation are automated; refer files only"),
    ("Earlier", "Fraud caught pre-sanction", "Document forensics + fraud graph run on every file, not samples"),
]
SCALE = [
    ("≤ 2 s", "Decision compute per file (prototype, 4 vCPU, synthetic data)"),
    ("> 40k / day", "Files per day on 4 vCPU at prototype speed (estimate, single node)"),
    ("< ₹1", "Compute cost per decision (estimate, excludes bureau/AA fees)"),
    ("Horizontal", "Stateless engines + queue → add workers per region"),
]
IMPACT_FOOT = ("All figures are TARGETS or ESTIMATES with stated assumptions, to be validated in a shadow-mode pilot; "
               "prototype measurements use 12 synthetic personas.")
MEASURES = ["Login-to-decision time", "Straight-through rate", "Refer reasons mix", "Agreement with credit officers",
            "Early delinquency (30+ DPD at 6 months)", "Fraud caught pre-sanction", "Override rate"]

ROADMAP = [
    ("Shadow pilot", "MONTHS 0–3", ["Run on historical files in parallel", "Calibrate model on Hero Housing book", "Tune policy YAML with credit team"]),
    ("Live STP", "MONTHS 3–6", ["Salaried Home Loans, 2 states", "AA + bureau live", "Refer queues with SLA"]),
    ("Scale", "MONTHS 6–12", ["Add LAP and self-employed", "Fraud graph across branches", "AVM across target cities"]),
    ("Govern", "ONGOING", ["Quarterly model validation", "Drift & fairness monitoring", "Policy impact simulation"]),
]
RISKS = [
    ("Model drift / thin data", "Shadow mode first; monotone, calibrated model; challenger; quarterly validation"),
    ("Data-source outage", "Timeouts and fallbacks; case referred with the gap visible — never guessed"),
    ("Regulatory change", "Thresholds in versioned YAML with citations; change without redeploying code"),
    ("Privacy & security", "Consent-first, PII masked at ingestion, encryption, India-region hosting"),
]

TEAM_LINE = ("We built a working prototype of this engine — document AI, policy engine, calibrated risk model, "
             "grounded copilot and audit ledger — and we would love to pilot it with Hero Housing Finance.")

# ----------------------------------------------------------------------------- appendix
SOURCES: list[tuple[int, str, str]] = [
    (1, "ICRA — Hero Housing Finance Ltd: ratings reaffirmed (27-Mar-2026)", "https://www.icra.in/Rating/GetRationalReportFilePdf?id=141946"),
    (2, "RBI — Report on Trend & Progress of Banking in India 2024-25 (frauds, App. Table IV.7)", "https://rbi.org.in/Scripts/PublicationsView.aspx?id=23648"),
    (3, "RBI (Housing Finance Companies) Directions, 2025 — RBI/DoR/2025-26/365 (paras 22, 58, 131–135, 144, 163, 215, 234, 236)", "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12939"),
    (4, "RBI (NBFC) Responsible Business Conduct Directions, 2025 — RBI/DOR/2025-26/362", "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12942"),
    (5, "RBI — Key Facts Statement for loans & advances, DOR.STR.REC.13/13.03.00/2024-25 (15-Apr-2024)", "https://www.rbi.org.in/Scripts/NotificationUser.aspx?Id=12663&Mode=0"),
    (6, "RBI (NBFC) KYC Directions, 2025 — RBI/DOR/2025-26/361 (paras 23, 27, 47, 49–51, 54, 63)", "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12943"),
    (7, "FIU-IND — Prevention of Money-Laundering Act, 2002 reporting", "https://fiuindia.gov.in/"),
    (8, "RBI Digital Lending Directions, 2025 — RBI/2025-26/36 (applies to HFCs)", "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12848"),
    (9, "Sahamati — Account Aggregator ecosystem statistics (Sep-2026); RBI NBFC-AA Directions 2025", "https://sahamati.org.in/?p=2028"),
    (10, "RBI (NBFC) Credit Risk Management Directions, 2025 — CERSAI, paras 25–28", "https://rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12954"),
    (11, "PIB — Digital Personal Data Protection Rules, 2025 backgrounder (Nov-2025)", "https://static.pib.gov.in/WriteReadData/specificdocs/documents/2025/nov/doc20251117695301.pdf"),
    (12, "UIDAI — What is masked Aadhaar", "https://uidai.gov.in/en/283-english-uk/faqs/aadhaar-online-services/e-aadhaar/1887-what-is-masked-aadhaar.html"),
    (13, "RBI — FREE-AI Committee report (13-Aug-2025)", "https://rbi.org.in/Scripts/PublicationReportDetails.aspx?ID=1306"),
    (14, "RBI (NBFC – Account Aggregator) Directions, 2025 — RBI/DoR/2025-26/368", "https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12936"),
    (15, "UN Security Council Consolidated List", "https://scsanctions.un.org/resources/xml/en/consolidated.xml"),
    (16, "UCI — Default of credit card clients dataset (benchmark)", "https://archive.ics.uci.edu/dataset/350/default+of+credit+card+clients"),
    (17, "RBI — Credit information reporting, fortnightly (RBI/2024-25/60, 8-Aug-2024)", "https://rbi.org.in/Scripts/NotificationUser.aspx?Id=12718"),
    (18, "Income Tax Dept — AIS / Form 26AS FAQ", "https://www.incometax.gov.in/iec/foportal/ais-faq"),
]

MATRIX = [
    ["PS2-1 Integrate data sources", "Slide 4 · connector layer, consent manager", "AA [9] [14], Digital Lending [8], DPDP [11]"],
    ["PS2-2 Eligibility & policy", "Slide 5 · policy YAML, FOIR/LTV engine", "HFC Directions para 58 [3]"],
    ["PS2-3 Fraud & KYC/AML", "Slide 6 · forensics, fraud graph, screening", "KYC Directions [6], FIU-IND [7], UN list [15]"],
    ["PS2-4 Risk scoring", "Slide 7 · calibrated PD, SHAP, fairness", "Prototype metrics; UCI benchmark [16]"],
    ["PS2-5 Documents & property", "Slide 8 · document AI, AVM, CERSAI", "HFC paras 58, 215 [3]; CERSAI [10]"],
    ["PS2-6 Compliance checks", "Slide 9 · rules with citations, KFS, FPC letters", "HFC paras 131–135, 234 [3]; KFS [5]; RBC [4]"],
    ["PS2-7 Instant decisioning", "Slide 10 · precedence, conditions, queues", "Prototype: 12/12 personas, ≤ 2 s"],
    ["PS2-8 Explainability & governance", "Slide 11 · ledger, replay, challenger", "FREE-AI [13]"],
    ["Judging: accuracy & feasibility", "Slides 7, 10, 13 · working prototype", "Measured on synthetic + public data"],
    ["Judging: use of data", "Slides 4, 7, 8", "12+ sources, AA-first"],
    ["Judging: explainability", "Slides 7, 10, 11", "SHAP + rule IDs + replay"],
    ["Judging: regulatory fit", "Slides 5, 6, 9, Appendix", "Cited paragraphs"],
    ["Judging: scalability", "Slides 12, 14", "Stateless engines, cost estimate"],
    ["Judging: clarity of presentation", "Slides 3, 13", "One-picture flow, prototype UI"],
]

# ----------------------------------------------------------------------------- notes for non-point slides
NOTES = {
    "title": ("Good morning. We are Team DoubleStack, and this is FinPilot HomeLoan — an explainable, humanless underwriting "
              "engine for Home Loans and Loans Against Property. In the next few minutes we'll show how a file goes from "
              "application to an audit-ready decision in minutes, how each of the eight required points is covered, and a "
              "working prototype we built to prove it."),
    "problem": ("Hero Housing Finance has a book of about seven thousand crore rupees, mostly Home Loans and LAP, across eleven "
                "states — mid-segment with a focus on affordable housing, according to ICRA. The book is young, and gross "
                "stage three rose from 1.7 to 2.4 percent in nine months. Loan files are also where fraud happens: banks reported "
                "almost thirty-two thousand crore of advance-related frauds last year. And the compliance load keeps growing. "
                "So the question is: how do you decide faster and more consistently without lowering the bar?"),
    "solution": ("Here is the whole engine in one picture. We ingest data with consent, verify documents, run KYC and AML, "
                 "assess income, property and fraud, score risk, and let the policy engine decide. Clean files come out "
                 "approved straight through with a KFS and sanction letter; exceptions go to the right queue with the "
                 "evidence ready. The policy engine always has the last word."),
    "architecture": ("The architecture is layered. Channels — the branch app, customer portal, partner APIs and the existing "
                     "LOS — call one API gateway. A stateful orchestrator runs the decision engines, which are stateless and "
                     "scale horizontally. Data sits in a case store, an encrypted document vault, a feature store and the "
                     "hash-chained audit ledger, all hosted in India. Governance — model registry, policy repo, monitoring — "
                     "wraps everything."),
    "ui": ("This is our working prototype, on synthetic applicants. Top left, the underwriter dashboard with every case and its "
           "outcome. Top right, the decision card with plain-English reasons and the path to approval. Bottom left, the fraud "
           "graph — this one is a design mockup of the next module. Bottom right, the audit trail, hash-chained and replayable."),
    "impact": ("What does this mean for Hero Housing? These are targets, with assumptions stated, to be validated in a pilot: "
               "decisions in minutes instead of days, half or more of files straight through, much less manual effort per "
               "file, and fraud caught before sanction. On scale, the prototype decides a file in about two seconds on a "
               "small machine — cost per decision is a rupee or less in compute."),
    "roadmap": ("We'd start in shadow mode: run the engine on historical files next to the current process and calibrate on "
                "Hero Housing's own book. Then go live for salaried Home Loans in two states, then add LAP and self-employed, "
                "with governance running throughout. The main risks — drift, outages, regulatory change and privacy — each "
                "have a concrete mitigation built into the design."),
    "team": ("Thank you. We've built a working prototype of this engine and we'd love the chance to pilot it with Hero Housing "
             "Finance. We're happy to take questions — and every regulation we cited is listed in the appendix."),
    "sources": "All external sources used in the deck. Prototype numbers come from our own repository on synthetic data.",
    "matrix": "This matrix maps each required point and judging criterion to the slide where it is covered and the evidence.",
}
