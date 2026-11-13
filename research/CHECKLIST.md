# Deck checklist — PS2 requirements and judging criteria

Deck: `out/DoubleStack_HeroHousing_PS2.pptx` / `.pdf` (16 main slides + 2 appendix slides).

## The 8 required points (official PS2 "What you need to do")

| # | Required point | Slide | What is visible on the slide |
|---|---|---|---|
| 1 | Integrate data sources | 4 (also 3, 12) | Consent → parallel fetch → normalise/mask → evidence store; 12 named sources; AA statistic [9]; Digital Lending / DPDP consent [8] [11] |
| 2 | Eligibility & policy | 5 | Income → FOIR → LTV → max loan; policy-as-code YAML with rule IDs; HFC Directions para 58 LTV slabs [3]; informal-income analytics |
| 3 | Fraud detection & KYC/AML | 6 | Document forensics, cross-checks, fraud graph, KYC/AML; KYC Directions 2025 paras 27, 54, 63 [6]; FIU-IND [7] |
| 4 | Risk scoring | 7 | 18 features → monotone GBM → calibration → grade + SHAP; prototype AUC/KS; public benchmark [16]; fairness |
| 5 | Documents & property | 8 | Document AI + property (title, CERSAI, AVM) → LTV on conservative value; HFC paras 58, 215 [3]; CERSAI [10] |
| 6 | Compliance checks | 9 | Regulation → rule → check → audit; FPC para 135, KFS [5], NHB paras 234/144 [3]; 5-year retention [6] |
| 7 | Instant decisioning | 10 (also 3) | Reject / refer / conditions / approve precedence; prototype 0.3–2 s, 12/12 personas; path to yes; refer queues |
| 8 | Explainability & governance | 11 (also 13 audit screen) | Reason codes, versioned hashes, hash-chained ledger, replay; overrides, challenger; FREE-AI Sutra 2, Recs 14/16/24 [13] |

## The 6 judging criteria

| Criterion | Slides | Evidence |
|---|---|---|
| Accuracy & feasibility of approach | 7, 10, 13, 14, 15 | Working prototype; measured AUC/KS on synthetic and public data; 12/12 persona outcomes; pilot measurement plan |
| Use of data | 1-slide flow 3, 4, 7, 8 | 12+ data sources, AA-first; bank-flow / GST analytics for informal income; comparables + circle rates |
| Explainability | 7, 10, 11, 13 | SHAP reason codes, rule IDs, fixed decision precedence, replay, audit trail screen |
| Regulatory fit | 4, 5, 6, 8, 9, 11, Appendix A/B | Every rule cites a paragraph of a current RBI direction; compliance matrix |
| Scalability | 12, 14 | Layered cloud-native architecture; ≤ 2 s per decision; throughput and cost estimates with assumptions |
| Clarity of presentation | 3, 13, all | One-picture flow; consistent header/footer; ≤ ~60 words of prose per slide; speaker notes on every slide |

## Quality gates

- [x] Every slide rendered to PNG (LibreOffice → PDF → pdftoppm) and inspected; overflow, overlap and wrapping fixed over three passes.
- [x] All 8 points have their own slide titled with the official point name.
- [x] Every external statistic or regulation is cited in Appendix A with a source URL (from `research/NOTES.md`).
- [x] Targets on slide 14 are labelled TARGET / ESTIMATE with assumptions; prototype numbers labelled synthetic.
- [x] No team member names anywhere in the deck.
- [x] No Hero Housing, E-Cell or IIT Bombay logos; text names only.
- [x] Speaker notes on all 18 slides.
- [x] Spell-check: no misspellings (flagged words are domain terms or British spellings).
- [x] PDF size about 2 MB (< 20 MB).
