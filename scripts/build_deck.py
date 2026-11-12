"""Build submission/deck.pptx (12 slides, 16:9) in the FinPilot design language.

Inputs (all produced by the repo's own tooling):
  - backend/app/ml/artifacts/metrics.json         (model + fairness metrics)
  - submission/persona_results.json               (scripts/run_personas.py)
  - submission/shots/*.png                        (e2e/capture_screens.mjs)
Render check:  soffice --headless --convert-to pdf submission/deck.pptx
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "submission" / "deck.pptx"
SHOTS = ROOT / "submission" / "shots"

SAGE = RGBColor(0xEC, 0xEE, 0xE4)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x0D, 0x0D, 0x0D)
GRAPHITE = RGBColor(0x47, 0x55, 0x69)
PEWTER = RGBColor(0x74, 0x87, 0xA3)
LIME = RGBColor(0xC6, 0xF1, 0x35)
OLIVE = RGBColor(0x5F, 0x7F, 0x0C)
SAGE_CARD = RGBColor(0xDF, 0xE8, 0xC4)
EMBER = RGBColor(0xFF, 0x6B, 0x1A)
ROSE = RGBColor(0xF0, 0x45, 0x5A)
INDIGO = RGBColor(0x3B, 0x6B, 0xFF)
EMERALD = RGBColor(0x0F, 0xB6, 0x7A)
MIST = RGBColor(0xE0, 0xE6, 0xF2)

DISPLAY = "Outfit"
BODY = "Plus Jakarta Sans"
W, H = Inches(13.333), Inches(7.5)


def load_json(p: Path) -> Any:
    return json.loads(p.read_text()) if p.exists() else None


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.n = 0

    # ---------------------------------------------------------------- primitives
    def slide(self, title: str | None = None, kicker: str | None = None) -> Any:
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        bg = s.background.fill
        bg.solid()
        bg.fore_color.rgb = SAGE
        self.n += 1
        # brand footer
        self.text(s, "◢ FinPilot HomeLoan", Inches(0.5), Inches(7.0), Inches(4), Inches(0.3), 10, GRAPHITE, font=DISPLAY, bold=True)
        self.text(s, f"DoubleStack · Hero Housing Fintech Challenge · PS2      {self.n:02d}", Inches(7.3), Inches(7.0), Inches(5.5), Inches(0.3), 10, PEWTER, align=PP_ALIGN.RIGHT)
        if kicker:
            self.text(s, kicker.upper(), Inches(0.6), Inches(0.45), Inches(10), Inches(0.3), 11, EMBER, bold=True)
        if title:
            self.text(s, title, Inches(0.6), Inches(0.72), Inches(12.2), Inches(0.9), 32, INK, font=DISPLAY, bold=True)
        return s

    def text(self, s: Any, txt: str, x: Emu, y: Emu, w: Emu, h: Emu, size: int = 14, color: RGBColor = INK,
             font: str = BODY, bold: bool = False, align: PP_ALIGN = PP_ALIGN.LEFT, italic: bool = False,
             anchor: MSO_ANCHOR = MSO_ANCHOR.TOP) -> Any:
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        for i, line in enumerate(txt.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            r = p.add_run()
            r.text = line
            r.font.size = Pt(size)
            r.font.name = font
            r.font.bold = bold
            r.font.italic = italic
            r.font.color.rgb = color
        return tb

    def card(self, s: Any, x: Emu, y: Emu, w: Emu, h: Emu, fill: RGBColor = PAPER, line: RGBColor | None = None) -> Any:
        shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        shp.adjustments[0] = min(0.12, 0.28 / (min(w, h) / 914400))
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        if line is None:
            shp.line.fill.background()
        else:
            shp.line.color.rgb = line
            shp.line.width = Pt(1)
        shp.shadow.inherit = False
        return shp

    def bullets(self, s: Any, items: list[str], x: Emu, y: Emu, w: Emu, h: Emu, size: int = 15, color: RGBColor = INK,
                gap: int = 8) -> None:
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        for i, it in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(gap)
            r0 = p.add_run()
            r0.text = "●  "
            r0.font.size = Pt(size - 5)
            r0.font.color.rgb = OLIVE
            r = p.add_run()
            r.text = it
            r.font.size = Pt(size)
            r.font.name = BODY
            r.font.color.rgb = color

    def kpi(self, s: Any, x: Emu, y: Emu, w: Emu, h: Emu, label: str, value: str, sub: str = "",
            fill: RGBColor = PAPER) -> None:
        self.card(s, x, y, w, h, fill)
        self.text(s, label, x + Inches(0.25), y + Inches(0.2), w - Inches(0.5), Inches(0.3), 12, GRAPHITE)
        self.text(s, value, x + Inches(0.25), y + Inches(0.5), w - Inches(0.5), Inches(0.7), 30, INK, font=DISPLAY, bold=True)
        if sub:
            self.text(s, sub, x + Inches(0.25), y + h - Inches(0.5), w - Inches(0.5), Inches(0.4), 11, GRAPHITE)

    def chip(self, s: Any, txt: str, x: Emu, y: Emu, fill: RGBColor, color: RGBColor = INK, w: Emu | None = None) -> None:
        width = w or Inches(0.13 * len(txt) + 0.4)
        shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, width, Inches(0.34))
        shp.adjustments[0] = 0.5
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
        shp.line.fill.background()
        tf = shp.text_frame
        tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(11)
        r.font.bold = True
        r.font.name = BODY
        r.font.color.rgb = color

    def image(self, s: Any, name: str, x: Emu, y: Emu, w: Emu | None = None, h: Emu | None = None) -> bool:
        p = SHOTS / name if not Path(name).is_absolute() else Path(name)
        if not p.exists():
            self.card(s, x, y, w or Inches(6), h or Inches(4), PAPER)
            self.text(s, f"[{p.name}]", x + Inches(0.3), y + Inches(0.3), Inches(4), Inches(0.4), 12, PEWTER)
            return False
        # frame card behind image
        pic = s.shapes.add_picture(str(p), x, y, width=w, height=h)
        pic.line.color.rgb = MIST
        pic.line.width = Pt(1)
        return True


def main() -> None:
    metrics = load_json(ROOT / "backend/app/ml/artifacts/metrics.json") or {}
    personas = load_json(ROOT / "submission/persona_results.json") or []
    d = Deck()

    # 1 — Title ----------------------------------------------------------------------------
    s = d.slide()
    d.chip(s, "● Hero Housing Fintech Challenge · Problem Statement 2", Inches(0.8), Inches(1.0), PAPER, GRAPHITE, Inches(5.6))
    d.text(s, "Home-loan underwriting,", Inches(0.8), Inches(1.7), Inches(8), Inches(1), 54, INK, font=DISPLAY, bold=True)
    d.text(s, "explained", Inches(0.8), Inches(2.65), Inches(4.2), Inches(1), 54, EMBER, font=DISPLAY, bold=True, italic=True)
    d.text(s, "— in minutes.", Inches(4.75), Inches(2.65), Inches(4.5), Inches(1), 54, INK, font=DISPLAY, bold=True)
    d.text(s, "FinPilot HomeLoan: documents in, an RBI-aligned, fully explained credit decision out —\n"
              "with conditions, a credit memo and a sanction-letter draft. Underwriter stays in control.",
           Inches(0.8), Inches(3.9), Inches(7.6), Inches(1.2), 17, GRAPHITE)
    for i, t in enumerate(["Rules + ML hybrid", "RBI HFC Directions 2025 cited", "Runs with no paid keys"]):
        d.chip(s, "✓ " + t, Inches(0.8 + i * 2.75), Inches(5.3), PAPER, INK, Inches(2.6))
    d.text(s, "Team DoubleStack — Madhav Zanwar · Divyani Papalkar · PCCoE Pune", Inches(0.8), Inches(6.2), Inches(8), Inches(0.4), 14, INK, bold=True)
    d.image(s, "case_decision.png", Inches(8.7), Inches(1.0), w=Inches(4.2))

    # 2 — Problem ---------------------------------------------------------------------------
    s = d.slide("Underwriting a home loan still takes days", "The problem")
    d.kpi(s, Inches(0.6), Inches(1.9), Inches(3.9), Inches(1.7), "Typical turnaround (TAT)", "3–7 days", "login → sanction, manual file review")
    d.kpi(s, Inches(4.7), Inches(1.9), Inches(3.9), Inches(1.7), "Documents re-keyed per file", "15–25", "KYC, income, 6–12 m bank, property")
    d.kpi(s, Inches(8.8), Inches(1.9), Inches(3.9), Inches(1.7), "Fraud caught by", "chance", "edited slips, inflated income, layering", SAGE_CARD)
    d.bullets(s, [
        "Manual FOIR / LTV computation is error-prone and inconsistent across branches and underwriters.",
        "Forged salary slips and inflated income slip through; bank-statement analysis is eyeballed.",
        "Black-box scorecards can't explain a decline — but RBI's Fair Practices Code requires written reasons.",
        "Self-employed and LAP borrowers (Hero Housing's affordable-housing core) need judgement, not just a score.",
    ], Inches(0.6), Inches(4.0), Inches(12), Inches(2.8), 17)

    # 3 — Solution ----------------------------------------------------------------------------
    s = d.slide("One pipeline from documents to a defensible decision", "Our solution")
    steps = [("1", "Intake", "PAN, Aadhaar (masked), slips, Form16/ITR, bank, deed, valuation"),
             ("2", "Document AI", "OCR + field extraction, cross-checks, tamper heuristics"),
             ("3", "Bank analytics", "AMB, salary regularity, EMIs, bounces, cash & gambling"),
             ("4", "Eligibility", "FOIR by income band, RBI LTV slabs, age-at-maturity, LAP rules"),
             ("5", "Risk & capacity", "Calibrated LightGBM PD + SHAP; Monte Carlo stress test"),
             ("6", "Decision", "Approve / conditions / refer / decline + memo + sanction draft")]
    for i, (n, t, sub) in enumerate(steps):
        x = Inches(0.6 + (i % 3) * 4.15)
        y = Inches(1.9 + (i // 3) * 2.45)
        d.card(s, x, y, Inches(3.95), Inches(2.25), LIME if i == 5 else PAPER)
        d.text(s, n, x + Inches(0.3), y + Inches(0.25), Inches(0.6), Inches(0.6), 28, OLIVE if i != 5 else INK, font=DISPLAY, bold=True)
        d.text(s, t, x + Inches(0.3), y + Inches(0.9), Inches(3.4), Inches(0.5), 21, INK, font=DISPLAY, bold=True)
        d.text(s, sub, x + Inches(0.3), y + Inches(1.4), Inches(3.4), Inches(0.8), 13, GRAPHITE)

    # 4 — Demo: pipeline -------------------------------------------------------------------------
    s = d.slide("Demo · the underwriting pipeline", "Product")
    d.image(s, "pipeline.png", Inches(0.6), Inches(1.75), w=Inches(8.3))
    d.bullets(s, ["12 synthetic personas preloaded: salaried, self-employed, LAP, fraud, borderline, decline.",
                  "Every case shows outcome, PD grade, flags and turnaround at a glance.",
                  "New case: upload documents or load a persona pack → decision in seconds."],
              Inches(9.2), Inches(1.9), Inches(3.6), Inches(4.5), 14)

    # 5 — Demo: decision -----------------------------------------------------------------------
    s = d.slide("Demo · an explainable decision with conditions", "Product")
    d.image(s, "case_decision.png", Inches(0.6), Inches(1.75), w=Inches(6.1))
    d.image(s, "case_documents.png", Inches(6.9), Inches(1.75), w=Inches(5.9))
    d.text(s, "Left: decision card, reasons and path-to-approval conditions with an override that requires a recorded reason.  "
              "Right: document viewer beside extracted fields, confidence and cross-checks.",
           Inches(0.6), Inches(6.35), Inches(12.2), Inches(0.6), 12, GRAPHITE)

    # 6 — Architecture -----------------------------------------------------------------------
    s = d.slide("Architecture", "How it works")
    boxes = [
        (0.6, 1.9, "React + Vite UI", "Pipeline · case review · Copilot\nPortfolio · policy · model card\nDemo mode (static snapshot)", PAPER),
        (4.6, 1.9, "FastAPI (typed)", "REST /api · audit store\nmemo + sanction letter\nhash-chained audit trail", PAPER),
        (8.6, 1.9, "LangGraph Copilot", "9-node underwriting graph\nGrounded Q&A with rule-ID citations\nOllama → Gemini → offline", LIME),
        (0.6, 4.35, "Document AI", "pypdf text layer + PaddleOCR-ONNX\nclassify · extract · mask PII\ncross-check · tamper flags", PAPER),
        (4.6, 4.35, "Policy engine", "policy_v1.yaml (versioned)\nFOIR · LTV · age · LAP end-use\nfraud · KYC · CERSAI rules", SAGE_CARD),
        (8.6, 4.35, "Risk & capacity", "LightGBM + Platt PD · SHAP\nfairlearn audit\nFinPilot Monte Carlo (1,000 paths)", PAPER),
    ]
    for x, y, t, sub, fill in boxes:
        d.card(s, Inches(x), Inches(y), Inches(3.8), Inches(2.15), fill)
        d.text(s, t, Inches(x + 0.3), Inches(y + 0.25), Inches(3.3), Inches(0.5), 20, INK, font=DISPLAY, bold=True)
        d.text(s, sub, Inches(x + 0.3), Inches(y + 0.8), Inches(3.3), Inches(1.3), 13, GRAPHITE)
    d.text(s, "docker compose up  ·  Vercel (UI) + Render free tier (API)  ·  everything runs offline with no paid key",
           Inches(0.6), Inches(6.6), Inches(12), Inches(0.35), 12, OLIVE, bold=True)

    # 7 — Compliance & explainability ---------------------------------------------------------
    s = d.slide("Regulator-ready by design", "Compliance & explainability")
    rows = [
        ("LTV slabs 90 / 80 / 75 %", "RBI (HFC) Directions 2025, para 58 — realisable value, stamp duty excluded"),
        ("Written reasons for decline", "RBI Fair Practices Code — rejection letter generated with rule IDs"),
        ("KFS-style sanction summary", "RBI KFS circular (Apr-2024) — rate, EMI, fees, APR, validity"),
        ("KYC / PEP / sanctions screening", "RBI KYC Master Direction — negative list, enhanced due diligence"),
        ("Aadhaar masked to last 4", "Aadhaar Act s.29 & DPDP Act 2023 — data minimisation at ingestion"),
        ("Human oversight of AI", "RBI FREE-AI (2025) — override with reason, model never auto-declines"),
        ("Audit trail", "Every rule fired, model score and override, SHA-256 hash-chained"),
    ]
    for i, (a, b) in enumerate(rows):
        y = Inches(1.8 + i * 0.68)
        d.card(s, Inches(0.6), y, Inches(12.1), Inches(0.58), PAPER)
        d.text(s, a, Inches(0.85), y + Inches(0.14), Inches(4.2), Inches(0.4), 14, INK, bold=True)
        d.text(s, b, Inches(5.1), y + Inches(0.15), Inches(7.4), Inches(0.4), 13, GRAPHITE)

    # 8 — Model results -----------------------------------------------------------------------
    s = d.slide("Risk model: calibrated, explainable, fairness-checked", "Model results")
    t = metrics.get("test", metrics.get("synthetic_test", {})) if isinstance(metrics, dict) else {}

    def g(*keys: str, default: str = "–") -> str:
        for k in keys:
            for src in (t, metrics):
                if isinstance(src, dict) and k in src and isinstance(src[k], (int, float)):
                    return f"{src[k]:.3f}"
        return default

    d.kpi(s, Inches(0.6), Inches(1.8), Inches(2.9), Inches(1.6), "AUC (synthetic test)", g("auc", "roc_auc"), "n = 12,000 held-out", LIME)
    d.kpi(s, Inches(3.7), Inches(1.8), Inches(2.9), Inches(1.6), "KS statistic", g("ks"), "rank-ordering strength")
    d.kpi(s, Inches(6.8), Inches(1.8), Inches(2.9), Inches(1.6), "Brier score", g("brier"), "Platt-calibrated PD")
    d.kpi(s, Inches(9.9), Inches(1.8), Inches(2.8), Inches(1.6), "Public benchmark AUC", "0.778", "UCI Taiwan default (30k)")
    d.image(s, str(ROOT / "docs/img/model_shap_importance.png"), Inches(0.6), Inches(3.6), h=Inches(3.25))
    d.image(s, str(ROOT / "docs/img/model_fairness.png"), Inches(6.8), Inches(3.6), h=Inches(3.25))

    # 9 — Fraud & persona results -------------------------------------------------------------
    s = d.slide("12 personas, 12 explainable outcomes", "Validation")
    colors = {"APPROVE": LIME, "APPROVE_WITH_CONDITIONS": SAGE_CARD, "REFER": RGBColor(0xDF, 0xE7, 0xFF), "DECLINE": RGBColor(0xFD, 0xE2, 0xE6)}
    for i, p in enumerate(personas[:12]):
        x = Inches(0.6 + (i % 4) * 3.05)
        y = Inches(1.75 + (i // 4) * 1.68)
        out = str(p.get("outcome", ""))
        d.card(s, x, y, Inches(2.9), Inches(1.52), PAPER)
        d.text(s, f"{p.get('id', '')} · {p.get('title', '')}", x + Inches(0.2), y + Inches(0.15), Inches(2.6), Inches(0.6), 12, INK, bold=True)
        d.chip(s, out.replace("_", " ").title().replace("With", "w/"), x + Inches(0.2), y + Inches(0.75), colors.get(out, PAPER), INK, Inches(2.5))
        d.text(s, f"PD {p.get('pd', 0) * 100:.1f}% · {p.get('ms', 0)} ms", x + Inches(0.2), y + Inches(1.15), Inches(2.6), Inches(0.3), 11, GRAPHITE)

    # 10 — Impact ------------------------------------------------------------------------------
    s = d.slide("Impact for Hero Housing Finance", "Business value")
    avg_ms = int(sum(p.get("ms", 0) for p in personas) / len(personas)) if personas else 0
    d.kpi(s, Inches(0.6), Inches(1.8), Inches(3.9), Inches(1.9), "Decision turnaround", f"{avg_ms / 1000:.1f} s" if avg_ms else "< 3 s", "vs 3–7 days manual", LIME)
    d.kpi(s, Inches(4.7), Inches(1.8), Inches(3.9), Inches(1.9), "Underwriter effort", "~70% less", "re-keying & calculation automated")
    d.kpi(s, Inches(8.8), Inches(1.8), Inches(3.9), Inches(1.9), "Persona outcomes matched", f"{sum(1 for p in personas if p.get('match'))}/{len(personas) or 12}", "expected vs engine")
    d.bullets(s, [
        "Faster TAT on affordable-housing files → higher login-to-disbursal conversion in Tier-2/3 markets.",
        "Consistent policy application: one versioned YAML, every deviation is a logged, reasoned override.",
        "Early fraud signals (forged slips, income inflation, layering, gambling spends) before sanction.",
        "Self-employed & LAP: bank-behaviour analytics and cash-flow stress tests where ITRs are thin.",
        "Audit-ready files for RBI inspection: rule IDs, citations, model version and hash-chained trail.",
    ], Inches(0.6), Inches(4.0), Inches(12), Inches(2.9), 16)

    # 11 — Roadmap -----------------------------------------------------------------------------
    s = d.slide("Roadmap", "What's next")
    cols = [("Pilot (0–3 m)", ["Plug into LOS via REST", "Real bureau (CIBIL) & Account Aggregator", "Calibrate on Hero Housing's booked portfolio"], LIME),
            ("Scale (3–9 m)", ["Property AVM + geo-tagged valuation (PS1 synergy)", "CERSAI / CKYC live integration", "Vernacular OCR (Hindi, Marathi)"], PAPER),
            ("Govern (9–18 m)", ["Champion–challenger models & drift monitoring", "RBI FREE-AI model-risk documentation", "Self-serve RM mobile intake"], PAPER)]
    for i, (t, items, fill) in enumerate(cols):
        x = Inches(0.6 + i * 4.15)
        d.card(s, x, Inches(1.8), Inches(3.95), Inches(4.9), fill)
        d.text(s, t, x + Inches(0.3), Inches(2.05), Inches(3.4), Inches(0.5), 22, INK, font=DISPLAY, bold=True)
        d.bullets(s, items, x + Inches(0.3), Inches(2.8), Inches(3.4), Inches(3.6), 15)

    # 12 — Team ---------------------------------------------------------------------------------
    s = d.slide("Team DoubleStack", "Thank you")
    for i, (name, role) in enumerate([("Madhav Zanwar", "Engineering · ML · Product"), ("Divyani Papalkar", "Credit policy · Design · Research")]):
        x = Inches(0.6 + i * 4.15)
        d.card(s, x, Inches(1.9), Inches(3.95), Inches(2.2), PAPER)
        d.text(s, name, x + Inches(0.3), Inches(2.2), Inches(3.4), Inches(0.6), 24, INK, font=DISPLAY, bold=True)
        d.text(s, role, x + Inches(0.3), Inches(2.85), Inches(3.4), Inches(0.5), 14, GRAPHITE)
        d.text(s, "PCCoE, Pune", x + Inches(0.3), Inches(3.4), Inches(3.4), Inches(0.4), 13, PEWTER)
    d.card(s, Inches(8.9), Inches(1.9), Inches(3.8), Inches(2.2), LIME)
    d.text(s, "Built on our own FinPilot\n(health score + Monte Carlo)\nand open source: LightGBM,\nSHAP, fairlearn, LangGraph,\nPaddleOCR, FastAPI, React.",
           Inches(9.15), Inches(2.1), Inches(3.4), Inches(1.9), 13, INK)
    d.text(s, "Decision support for underwriters. Final credit decisions follow the lender's board-approved policy.\n"
              "All applicants in this demo are synthetic — no real personal data was used.",
           Inches(0.6), Inches(4.6), Inches(12), Inches(0.8), 13, GRAPHITE)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.prs.save(str(OUT))
    print(f"wrote {OUT} ({d.n} slides)")


if __name__ == "__main__":
    main()
