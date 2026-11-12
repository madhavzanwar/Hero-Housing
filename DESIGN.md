# DESIGN.md — FinPilot HomeLoan design system

FinPilot HomeLoan reuses the visual language of **FinPilot** (our own app,
[VeerbhadraMahant/finpilot](https://github.com/VeerbhadraMahant/finpilot)). This
document was written after running FinPilot locally and walking every route
(landing, login, dashboard, transactions, budgets, goals, copilot, simulate,
plan, forecast & risk, scenarios, financial security, evidence council, risk
council, agent ops, statement, upload, connectors, household, tax, twin, my
data, profile, scheme analyst, web intel, pay) in light, dark-sidebar and mobile
views, and reading its `globals.css`, `NavShell`, `AppSidebar`, `Card`,
`KpiCard`, `StatTile`, `Chip`, `Button`, `ConfidenceChip` and
`HealthScoreCard`. Where FinPilot is a personal-finance app, every pattern below
is mapped onto an underwriting screen.

> One sentence: **a calm, graph-paper sage canvas, white 28 px bento cards,
> one electric-lime accent for "act here", Ember orange reserved for risk
> emphasis, Outfit display numbers and Plus Jakarta Sans body, with every
> number explainable.**

---

## 1. Principles (carried over from FinPilot)

1. **Explained, not just reported.** FinPilot's hero line is "Your financial
   health, *explained* — not just reported." Every figure on our screens links
   to its basis: the rule ID, document or formula (FinPilot's "Basis: …" lines
   under Budgets and Forecast & Risk).
2. **Three lanes, never blurred.** FinPilot separates *Observed facts*,
   *Model predictions* (with confidence) and *Recommended actions*. Our decision
   card, credit memo and Copilot answers use the same three lanes:
   **Evidence** (documents, bank analytics) → **Assessment** (eligibility math,
   PD + SHAP, Monte Carlo) → **Decision & conditions**.
3. **Confidence shown where information is incomplete.** FinPilot's
   `ConfidenceChip` fades from solid to dashed as confidence drops; we use the
   same chip for OCR field confidence and model calibration.
4. **Bento density without clutter.** Many small cards, each answering one
   question with a big number, a one-line sub-caption and, optionally, a
   sparkline.
5. **One primary action per view.** Lime (or navy) fill for the single CTA;
   everything else is ghost or outline.
6. **Honest disclaimers in-line.** FinPilot ends pages with small pewter notes
   ("Checks run on your own transactions… They point at things worth a look,
   not proof of fraud."). Ours: *"Decision support for underwriters. Final
   credit decisions follow the lender's policy."*

---

## 2. Tokens

Defined once as CSS variables (`frontend/src/index.css`) and exposed to
Tailwind v4 through `@theme inline`, exactly like FinPilot.

### 2.1 Colour — light (FinPilot values)

| Token | Value | Use |
|---|---|---|
| `--background` | `#eceee4` | Pale sage canvas, overlaid with a 44 px graph-paper grid (`rgba(13,13,13,.035)` hairlines), `background-attachment: fixed` |
| `--surface` / `--color-paper` | `#ffffff` | Cards |
| `--color-fog` | `#f1f2ec` | Inner wells, table header rows, chip fills |
| `--sidebar` | `#f8f9ef` | Floating sidebar panel |
| `--color-ink` | `#0d0d0d` | Primary text, numbers |
| `--color-graphite` | `#475569` | Secondary text |
| `--color-pewter` | `#7487a3` | Tertiary text, captions, uppercase labels |
| `--color-mist` | `#e0e6f2` | Hairline borders, inputs |
| `--color-lime` | `#c6f135` | **Signature accent**: active nav pill, primary CTA, highlight cards, selected segmented tab |
| `--color-lime-dark` | `#a6d11a` | Lime hover, borders on lime |
| `--color-olive` | `#5f7f0c` | Sparklines and gauge strokes on lime/sage, chart P50 line |
| `--color-sage` | `#dfe8c4` | Soft highlight card fill (health gauge well, "Money out" card) |
| `--tint-lime` | `#eefacc` | Copilot message bubbles, selected rows |
| `--color-ember` | `#ff6b1a` | Brand dot, italic hero word, **risk emphasis** (reduce-to amounts, overdue) |
| `--color-ember-dark` | `#e0540a` | Ember text on light fills |
| `--color-navy` | `#172554` | Secondary solid CTA ("Add Goal", "Confirm Classification") → our "Apply override" |
| `--color-leaf` | `#0fb67a` | Positive / pass |
| `--color-sun` | `#ffb81f` | Warn |
| `--badge-rose` | `#f0455a` | Fail / decline |
| `--badge-indigo` | `#3b6bff` | Info / refer |
| `--badge-cyan` | `#12a5b8` | Neutral data series |

Semantic badge pairs (fg / 12 % bg), from FinPilot: emerald `#0fb67a`,
amber `#e09400`, rose `#f0455a`, indigo `#3b6bff`, cyan `#12a5b8`.

**Decision outcome colours** (new, built from the same palette):

| Outcome | Fill | Text | Chip |
|---|---|---|---|
| APPROVE | `--color-lime` | ink | "Approved" |
| APPROVE_WITH_CONDITIONS | `--color-sage` + lime-dark border | ink | "Approved with conditions" |
| REFER | `--badge-indigo-bg` | indigo | "Refer to underwriter" |
| DECLINE | `--badge-rose-bg` | rose | "Declined" |

**Severity**: CRITICAL rose solid · HIGH rose tint · MEDIUM amber tint ·
LOW emerald tint · INFO fog. This matches FinPilot's Financial Security "Findings
by severity" tiles (rose / amber / sage squares with a big digit).

**Charts** (FinPilot `--chart-*`): series 1 olive `#5f7f0c`, 2 ember
`#ff6b1a`, 3 indigo `#3b6bff`, 4 emerald `#0fb67a`, 5 amber `#e09400`,
6 cyan `#12a5b8`. P10–P90 bands use `--color-sage` at 70 %; reserve and limit
lines are dashed rose `#f0455a`.

### 2.2 Colour — dark

FinPilot only darkens the sidebar (`hsl(240 5.9% 10%)` panel with lime
active pill). We extend that into a full dark theme with the same accents:

| Token | Dark value |
|---|---|
| `--background` | `#0e0f0b` + grid at `rgba(255,255,255,.035)` |
| `--surface` | `#17191a` |
| `--color-fog` | `#202322` |
| `--sidebar` | `#121412` |
| `--color-ink` (text) | `#f3f5ee` |
| `--color-graphite` | `#b4bcc8` |
| `--color-pewter` | `#8792a6` |
| `--color-mist` (borders) | `rgba(255,255,255,.08)` |
| `--color-sage` | `#26301a` |
| `--tint-lime` | `#1f2a0d` |
| lime / ember / navy | unchanged (`#c6f135` / `#ff6b1a`, navy → `#3b5bdb` for contrast) |

Toggle: `.dark` on `<html>`, persisted in `localStorage("fphl:theme")`,
defaulting to `prefers-color-scheme`.

### 2.3 Typography

| Role | Font | Spec |
|---|---|---|
| Display: page titles, card titles, every big number | **Outfit Variable** (`.font-display`) | 500–600, tracking `-0.025em`; KPI 28–36 px; hero 56–72 px |
| UI / body | **Plus Jakarta Sans Variable** | 400/500/600, 13–15 px, tracking `-0.005em` |
| Labels | Jakarta 600, 11 px, `uppercase tracking-wider text-pewter` | "INCOME / MO", "SAVED", "REQUIRED PACE" |
| Numbers | `.tnum` (`tabular-nums`, `-0.02em`) | every ₹ value; paise in a smaller pewter span (`₹4,05,000`**`.00`**) |
| Mono | `ui-monospace` 11 px | rule IDs (`ELG-FOIR-02`), doc refs, hashes, env-key names |

Money is always Indian-grouped (`₹1,00,157`, `₹45,00,000`), with short forms
`₹45L` / `₹1.1Cr` in dense tables.

### 2.4 Shape, elevation, motion

- Radii: `--radius-card: 28px` (bento cards), `--radius-surface: 16px`
  (inner wells, sub-score tiles), `--radius-chip: 10px` (chips, inputs,
  buttons). Pills (`rounded-full`) for segmented controls, nav and persona
  switcher.
- `.elevation-card`: white, `1px rgba(13,13,13,.04)` border,
  `0 1px 2px rgba(13,13,13,.04), 0 10px 24px -16px rgba(13,13,13,.18)`.
- `.elevation-card-hover`: lift −3 px, lime-dark border at 55 %, olive glow.
- Durations 150 / 200 / 300 ms; spring `cubic-bezier(.16,1,.3,1)`; page enter
  `opacity 0→1, y 10→0, 350 ms` (framer-motion); active pills slide with
  `layoutId` (stiffness 450, damping 35). `prefers-reduced-motion` disables
  all of it.
- Skeletons: `animate-skeleton-pulse` blocks shaped like the final card.
- Scrollbars hidden app-wide (FinPilot); content still scrolls.

---

## 3. Layout shell (FinPilot `NavShell` + `AppSidebar`)

```
┌──────────────┬───────────────────────────────────────────────────────────┐
│ ◢ FinPilot ● │ ☰ │ Page title (Outfit 24–36)   [Search ⌘K] [🌓] [● RM] [🔔]│  ← sticky 64 px, bg-background/70 + blur
│  HomeLoan    ├───────────────────────────────────────────────────────────┤
│              │  Section heading (Outfit 28)          [ghost] [ghost] [CTA]│
│ UNDERWRITING │  subtitle in graphite                                     │
│ ▣ Pipeline   │  ┌ KPI ┐┌ KPI ┐┌ KPI ┐┌ lime KPI ┐                         │
│ ⊕ New case   │  └─────┘└─────┘└─────┘└──────────┘                         │
│ ✦ Copilot    │  ┌──────── bento card ────────┐┌── card ──┐              │
│ INSIGHT      │  │                            ││          │              │
│ ◔ Portfolio  │  └────────────────────────────┘└──────────┘              │
│ ⚖ Policy     │                                                           │
│ ◎ Model card │                                         (💬 floating lime │
│ ▤ Audit      │                                          Copilot button)  │
│ [lime CTA]   │                                                           │
└──────────────┴───────────────────────────────────────────────────────────┘
```

- **Sidebar**: floating panel (`variant="floating"`, 12 px inset, 28 px
  radius, `--sidebar` fill), collapsible to icons. Group labels in pewter 12 px
  ("Copilot", "Track", "Intelligence" in FinPilot → **Underwriting**,
  **Insight**, **Governance** here). Each group has its own icon tint (ember,
  emerald, indigo, as in FinPilot). The active item is a full-width **lime
  pill** with ink text. The footer holds a full-width lime button ("New case").
- **Header**: sticky, translucent; breadcrumb title in Outfit. On the right a
  search pill (white, `⌘K` kbd), an icon button for theme, the **persona /
  role switcher** (FinPilot's Priya · Arjun · Meera segmented pill with an
  ember dot on the active one → our *RM · Underwriter · Credit head* role pill),
  and a notifications bell with an ember count badge.
- **Main**: `max-w-[1600px]`, padding 16/24/32 px by breakpoint, `gap-4`
  between bento rows.
- **Floating Copilot**: lime 56 px circle bottom-right (FinPilot chat
  bubble), opens a right-side sheet with case-scoped chat.
- **Mobile**: sidebar becomes an off-canvas sheet; KPI grids collapse to two
  columns, then one; tables scroll horizontally inside their card.

---

## 4. Components (FinPilot source → our use)

| Component | FinPilot reference | Spec | Used for |
|---|---|---|---|
| **Card** | `ui/Card` | `rounded-card elevation-card p-4 sm:p-5`; `CardTitle` 16 px semibold, or Outfit 18 px for section cards | everything |
| **KpiCard** | `dashboard/KpiCard` | label (14 px graphite) + icon in a 36 px round chip top-right; Outfit 30 px value; sub-line; optional olive sparkline bleeding to the card edge; variants `white`, `lime`, `sage` | Pipeline counts, max eligible loan, EMI, PD |
| **StatTile** | `ui/StatTile` | uppercase 11 px label, Outfit 24–30 px value, 12 px sub, trend chip | dense KPI strip (FinPilot's 8-up "INCOME / MO · SPEND / MO …" row) → FOIR · LTV · AMB · Bounces · Income used · Age at maturity · PD · Health |
| **Chip** | `ui/Chip` | 10 px radius, tones neutral / accent / outline / success / warning / danger / info | statuses, doc types, rule outcomes |
| **ConfidenceChip** | `ui/ConfidenceChip` | solid emerald ≥ 75 %, fog ≥ 45 %, dashed below | OCR field confidence, classification confidence |
| **Button** | `ui/Button` | `lime` (primary), `navy` (secondary solid), `secondary` (hairline), `ghost`; min-h 36/44/48 | CTA rules: one lime per view |
| **Segmented tabs** | Forecast & Risk ("Forecast · Risk · Scenarios · Model accuracy · Assumptions"), Outlook ("Spending mix · 90-day cash flow · Net worth") | white pills, active = lime fill; or a dark-slate track with a white active pill | case-detail tabs |
| **Gauge** | `HealthScoreCard` | 160 px SVG arc, olive stroke on a white track inside a sage well, Outfit 48 px score, "out of 100"; status chip ("Optimal Health") | Repayment health score; PD → score 300–900 gauge |
| **Sub-score tiles** | Health index pillars | white 16 px tiles: name + "Weight: 30%" mini-chip + `78 /100`, 8 px bar (emerald/amber/rose by score), one-line basis | FinPilot 5 pillars; eligibility checks (FOIR, LTV, age, bureau, banking) as pass/warn/fail tiles |
| **Severity tiles** | Financial Security "Findings by severity" | 3 square tiles (rose / amber / sage) with a big digit and label | Fraud & compliance flags count |
| **Findings list** | Financial Security "Top findings" | fog rows: severity chip, bold title, 12 px explanation, right-aligned ₹ amount | Fraud flags, document tamper flags, rules fired |
| **Copilot analysis card** | "Copilot's analysis" (sage card) | sparkle icon + bold summary sentence, paragraph, numbered "WHAT TO DO", footnote "Written by FinPilot from your own records (offline summary)" | Decision rationale and conditions |
| **Lime highlight card** | "How to trim rent & housing by **(25%)**?" | full lime card, Outfit 32 px question with a circled number, white pill button at the bottom | "How to get to approval: reduce to ₹X **or** add co-applicant" |
| **Fan chart** | Forecast & Risk "Cash balance forecast" | olive P50 line, sage P10–P90 band, dashed rose reserve line, Recharts | Monte Carlo buffer after EMI |
| **Data table** | Transactions / Monthly forecast | 13 px rows, 1 px hairlines, header in graphite 12 px, ranges in pewter parentheses `₹13,003 (₹-85,035 to ₹1,12,935)`, right-aligned tabular numbers | bank months, tenure options, rules fired |
| **Transaction row** | Transactions "All transactions" | merchant avatar, status chip ("To review" amber / "Reviewed" emerald), signed amount, category chip with icon | bank-statement viewer with category chips (SALARY, EMI, BOUNCE, CASH, HIGH-RISK) |
| **Agent graph** | Evidence Council radial graph | centre "Your ledger" doc card, agent nodes on a soft lime radial gradient, each with icon + state ("Waiting", "Done") | LangGraph Underwriting Copilot trace: intake → documents → … → memo |
| **Agent ops table** | Agent Ops "Agents, their jobs and models" | Agent · Task · Model → backup · Behaviour | Copilot node trace with ms timings, LLM engine in use |
| **Statement document** | Executive Health Statement | white A4 sheet inside the page: doc ref (mono, right), "SECTION 01" ember labels + uppercase headings, tables, print stylesheet | Credit memo & sanction letter (print / save PDF) |
| **Pill chips row** | Copilot suggestion chips | white outline pills, 13 px | suggested Copilot questions |
| **Chat** | Copilot page | left rail of chats (sage), centre: "Hey, Priya. Ready to dive in?" Outfit 36 px; lime-tint message bubbles with a lime sparkle avatar; large input with helper footnote | Underwriter Q&A grounded in the case |
| **Empty state** | "No report yet. Press Run investigation" | centred pewter 13 px, an icon, one action | empty pipeline, no flags |
| **Gradient money tiles** | Transactions top row (soft iridescent gradients) | used sparingly for the 3 hero numbers | Portfolio: sanctioned value, approval rate, average TAT |

Icons: **lucide-react**, 16–18 px, stroke 1.75; the group tint applies only in
the sidebar.

---

## 5. Screens

### 5.1 Landing (`/`), FinPilot landing
Sage graph-paper hero with a radial mask, a centred pill badge ("● Hero Housing
Fintech Challenge · PS2"), Outfit 64–72 px headline *"Home-loan underwriting,
**explained** — in minutes."* with **explained** in ember italic, a graphite
subline, a lime CTA "Open the pipeline →" and a white "Try a persona", plus a
row of ✓ pills ("Rules + ML hybrid", "Works offline — no paid keys", "RBI LTV
caps cited"). Below it: a 4-card "Engineered for…" bento (Document AI ·
Eligibility engine · Explainable risk · Underwriting Copilot), "Test drive on
12 curated personas" cards (avatar initial, colour-coded tag such as "Fraud
case" or "LAP", one-line story, "Load case →"), and a sage CTA band.

### 5.2 Case pipeline (`/pipeline`), FinPilot Dashboard
- Header: "Underwriting pipeline" + subline; ghost buttons "Refresh",
  "Reset demo"; lime "New case".
- 8-up **StatTile strip**: In queue · Approved · With conditions · Referred ·
  Declined · Avg TAT · Fraud flagged · Sanctioned ₹.
- Bento row: an "Approval mix" donut card (FinPilot "Where your money went"),
  "Decisions by product" bars (FinPilot "Monthly spend"), and a lime highlight
  card "3 cases need you" → filter to Refer.
- **Cases table** (FinPilot Transaction History): applicant avatar + name +
  persona tag · product chip · amount / property value · LTV · PD chip with
  grade · flags (rose count) · outcome chip · TAT · "Open →".

### 5.3 New case (`/cases/new`), FinPilot Upload + Goals form
A form card (Goal form styling: 4-column labelled inputs, "Starter
Blueprints" chips → **persona quick-fill chips**), a drop zone card ("Choose
files", "Scan with camera"-style pair of buttons, accepted types footnote),
the file list with detected doc type + ConfidenceChip, and a lime "Run
underwriting" button. While it runs: the **agent graph** animates node by node
with timings, then routes to the case.

### 5.4 Case detail (`/cases/:id`), FinPilot Forecast & Risk + Financial Security + Statement
- **Case header card**: applicant name (Outfit 28), product · city ·
  employment chips, masked PAN/Aadhaar in mono, status chip, buttons "Credit
  memo", "Sanction letter", lime "Ask Copilot".
- **Decision hero row** (4 KPI cards, as in Forecast & Risk): (1) a lime or
  outcome-coloured **Decision** card with outcome, sanction amount, EMI × tenure
  @ rate, decided in N ms; (2) **Max eligible loan** with a binding-constraint
  sub ("limited by FOIR"); (3) **PD / score** with grade chip and band;
  (4) **Repayment health** gauge mini with P(shortfall).
- **Segmented tabs**: *Decision · Documents · Bank analytics · Eligibility ·
  Risk & SHAP · Capacity · Fraud & compliance · Rules fired · Memo · Audit*.
  - **Decision**: Copilot-analysis card (reasons, numbered conditions), lime
    "path to approval" card, and an **override panel** (navy CTA, required
    reason, underwriter name, outcome segmented control, optional amount).
  - **Documents**: left list of documents (type chip, OCR engine, flags count);
    right the **document viewer** (PDF/PNG in a white sheet) beside an
    extracted-fields table (field · value · ConfidenceChip · source) and the
    cross-check matrix (name / DOB / address / employer / salary vs credit →
    ✓ / ✕ per document).
  - **Bank analytics**: StatTile strip (AMB, avg salary credit, regularity,
    EMIs detected, bounces, cash share), monthly credits vs debits bars
    (FinPilot "Money in vs money out": olive and ember bars), and a transactions
    table with category chips.
  - **Eligibility**: sub-score tiles for FOIR (actual vs cap, rule ID), LTV
    (actual vs slab cap, RBI citation), age at maturity, tenure; a
    tenure-options table; and an "income basis" note.
  - **Risk & SHAP**: horizontal diverging bar chart (rose = increases risk,
    emerald = decreases), plain-language reason list, model version chip, and a
    "rules dominate the model" hybrid explainer.
  - **Capacity**: FinPilot 5-pillar health index card (gauge + tiles) and the
    fan chart of buffer after EMI over 24 months with the stress-test result.
  - **Fraud & compliance**: severity tiles and the findings list.
  - **Rules fired**: table rule ID (mono) · name · category chip · outcome chip
    · detail · effect · reference (pewter, truncates with a tooltip).
  - **Memo**: Executive-Statement style A4 document with print / save PDF.
  - **Audit**: vertical timeline (actor chip, action, detail, hash prefix in
    mono), plus the LangGraph agent trace table.

### 5.5 Copilot (`/copilot`), FinPilot Copilot
Case picker in the left rail; centre greeting "Hey, underwriter. Which case
are we looking at?"; suggestion pills ("Why was this referred?", "What if
tenure is 300 months?", "Which rules failed?", "What documents are missing?");
lime-tint answer bubbles with **citation chips** (`ELG-FOIR-02`,
`LTV-HL-02`, `doc: salary_slip_2`) and an engine chip ("grounded-template",
"ollama:llama3.2", "gemini").

### 5.6 Portfolio (`/portfolio`), FinPilot Statement / Dashboard analytics
Gradient hero tiles (sanctioned value, approval rate, average TAT vs a
manual-baseline benchmark), outcome donut, grade distribution bars, product
mix, "top rules fired" findings list, and override rate.

### 5.7 Policy (`/policy`) and Model card (`/model`)
Policy: version chip, each YAML section as a card with a mono key/value table
and citations. Model card: metric KPI strip (AUC, KS, Brier, ECE), ROC,
calibration and fairness images, and a limitations list.

---

## 6. Content and voice

- Plain English, second person for the underwriter ("You can approve this
  with one condition").
- Numbers first: "FOIR 62 % vs 55 % cap" rather than "high FOIR".
- Every rule mention carries its ID in mono.
- Never show a full PAN or Aadhaar; masks look like `XXXXX1234F` and
  `XXXX XXXX 1234`.
- Footnote on every decision surface: *"Decision support for underwriters.
  Final credit decisions follow the lender's board-approved policy."*

## 7. Accessibility

- Text contrast ≥ 4.5:1. Ink on lime passes; never put white text on lime.
- Focus ring `2px navy` (dark: lime) with a 2 px offset.
- Charts carry text equivalents (legend values + tables).
- Hit targets ≥ 36 px (44 px on touch).
- Status is never conveyed by colour alone: chips always carry a word.
