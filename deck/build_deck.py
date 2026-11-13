"""Build the PS2 solution deck: out/DoubleStack_HeroHousing_PS2.pptx (16 slides + 2 appendix).

python-pptx, native editable shapes; one font (Plus Jakarta Sans), one accent (lime / olive).
Content facts live in deck/content.py (every external fact cited in the appendix).
Render check:  soffice --headless --convert-to pdf out/*.pptx && pdftoppm -r 80 -png out/*.pdf out/png/s
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).parent))
import content as C  # noqa: E402

ICONS = ROOT / "deck/assets/icons"
SCREENS = ROOT / "deck/assets/screens"
OUT = ROOT / "out/DoubleStack_HeroHousing_PS2.pptx"

FONT = "Plus Jakarta Sans"
BG = RGBColor(0xF6, 0xF7, 0xF1)
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
INK = RGBColor(0x11, 0x14, 0x0F)
GRAPHITE = RGBColor(0x45, 0x50, 0x5E)
PEWTER = RGBColor(0x6B, 0x77, 0x88)
LINE = RGBColor(0xDD, 0xE1, 0xD6)
FOG = RGBColor(0xEE, 0xF0, 0xE8)
LIME = RGBColor(0xC6, 0xF1, 0x35)      # the accent
OLIVE = RGBColor(0x4F, 0x6A, 0x08)     # accent, text-safe shade
TINT = RGBColor(0xEE, 0xF8, 0xCF)      # accent, light tint
W, H = Inches(13.333), Inches(7.5)
MX = Inches(0.6)                        # side margin


def rgb_hex(c: RGBColor) -> str:
    return str(c)


class Deck:
    def __init__(self) -> None:
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = W, H
        self.n = 0

    # ------------------------------------------------------------------ primitives
    def new(self, title: str, kicker: str = "", notes: str = "", header: bool = True) -> Any:
        s = self.prs.slides.add_slide(self.prs.slide_layouts[6])
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = BG
        self.n += 1
        if header:
            if kicker:
                self.text(s, kicker.upper(), MX, Inches(0.42), Inches(9), Inches(0.3), 11, OLIVE, bold=True, spacing=1.5)
            self.text(s, title, MX, Inches(0.68), Inches(12.1), Inches(0.75), 28, INK, bold=True)
            self.footer(s)
        if notes:
            s.notes_slide.notes_text_frame.text = notes
        return s

    def footer(self, s: Any) -> None:
        self.box(s, MX, Inches(7.0), W - 2 * MX, Emu(9525), LINE, None, 0, MSO_SHAPE.RECTANGLE)
        self.text(s, "Team DoubleStack  |  PS2", MX, Inches(7.1), Inches(4), Inches(0.25), 9.5, PEWTER)
        self.text(s, "FinPilot HomeLoan", Inches(5.2), Inches(7.1), Inches(3), Inches(0.25), 9.5, PEWTER, align=PP_ALIGN.CENTER)
        self.text(s, f"{self.n:02d}", W - MX - Inches(1), Inches(7.1), Inches(1), Inches(0.25), 9.5, PEWTER, align=PP_ALIGN.RIGHT)

    def text(self, s: Any, txt: str, x: Emu, y: Emu, w: Emu, h: Emu, size: float = 14, color: RGBColor = INK,
             bold: bool = False, align: PP_ALIGN = PP_ALIGN.LEFT, anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
             spacing: float = 0, line: float = 1.12, italic: bool = False) -> Any:
        tb = s.shapes.add_textbox(x, y, w, h)
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = anchor
        for i, ln in enumerate(txt.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = line
            self._runs(p, ln, size, color, bold, spacing, italic)
        return tb

    def _runs(self, p: Any, ln: str, size: float, color: RGBColor, bold: bool, spacing: float = 0,
              italic: bool = False) -> None:
        # **bold** segments
        parts = ln.split("**")
        for j, seg in enumerate(parts):
            if not seg:
                continue
            r = p.add_run()
            r.text = seg
            f = r.font
            f.size = Pt(size)
            f.name = FONT
            f.bold = bold or (j % 2 == 1)
            f.italic = italic
            f.color.rgb = color
            if spacing:
                r._r.get_or_add_rPr().set("spc", str(int(spacing * 100)))

    def box(self, s: Any, x: Emu, y: Emu, w: Emu, h: Emu, fill: RGBColor = PAPER, line: RGBColor | None = None,
            radius: float = 0.12, shape: MSO_SHAPE = MSO_SHAPE.ROUNDED_RECTANGLE, lw: float = 1) -> Any:
        b = s.shapes.add_shape(shape, x, y, w, h)
        if shape == MSO_SHAPE.ROUNDED_RECTANGLE:
            short = min(w, h) / 914400
            b.adjustments[0] = min(0.5, radius / max(short, 0.01))
        b.fill.solid()
        b.fill.fore_color.rgb = fill
        if line is None:
            b.line.fill.background()
        else:
            b.line.color.rgb = line
            b.line.width = Pt(lw)
        b.shadow.inherit = False
        b.text_frame.margin_left = b.text_frame.margin_right = Inches(0.08)
        return b

    def boxtext(self, s: Any, x: Emu, y: Emu, w: Emu, h: Emu, txt: str, size: float = 12, fill: RGBColor = PAPER,
                color: RGBColor = INK, bold: bool = False, line: RGBColor | None = LINE, align: PP_ALIGN = PP_ALIGN.CENTER,
                radius: float = 0.12) -> Any:
        b = self.box(s, x, y, w, h, fill, line, radius)
        tf = b.text_frame
        tf.word_wrap = True
        tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_top = tf.margin_bottom = Inches(0.03)
        for i, ln in enumerate(txt.split("\n")):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = align
            p.line_spacing = 1.05
            self._runs(p, ln, size if i == 0 else size - 1.0, color if i == 0 else GRAPHITE, bold if i == 0 else False)
        return b

    def icon(self, s: Any, name: str, x: Emu, y: Emu, size: Emu, tone: str = "olive", chip: RGBColor | None = TINT) -> None:
        if chip is not None:
            c = s.shapes.add_shape(MSO_SHAPE.OVAL, x, y, size, size)
            c.fill.solid()
            c.fill.fore_color.rgb = chip
            c.line.fill.background()
            pad = int(size * 0.24)
            s.shapes.add_picture(str(ICONS / f"{name}-{tone}.png"), x + pad, y + pad, size - 2 * pad, size - 2 * pad)
        else:
            s.shapes.add_picture(str(ICONS / f"{name}-{tone}.png"), x, y, size, size)

    def arrow(self, s: Any, x1: Emu, y1: Emu, x2: Emu, y2: Emu, color: RGBColor = PEWTER, w: float = 1.25) -> None:
        c = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
        c.line.color.rgb = color
        c.line.width = Pt(w)
        ln = c.line._get_or_add_ln()
        tail = ln.makeelement(qn("a:tailEnd"), {"type": "triangle", "w": "med", "len": "med"})
        ln.append(tail)

    def chips(self, s: Any, items: list[str], x: Emu, y: Emu, w: Emu, size: float = 10.5, fill: RGBColor = PAPER,
              gap: float = 0.08, height: float = 0.32) -> Emu:
        cx, cy = x, y
        for it in items:
            cw = Inches((0.083 if size >= 10.5 else 0.076) * len(it) + 0.34)
            if cx + cw > x + w:
                cx = x
                cy += Inches(height + gap)
            b = self.boxtext(s, cx, cy, cw, Inches(height), it, size, fill, INK, False, LINE, radius=0.16)
            b.text_frame.word_wrap = False
            cx += cw + Inches(gap)
        return cy + Inches(height)

    def picture(self, s: Any, path: Path, x: Emu, y: Emu, w: Emu | None = None, h: Emu | None = None,
                frame: bool = True) -> Any:
        pic = s.shapes.add_picture(str(path), x, y, width=w, height=h)
        if frame:
            pic.line.color.rgb = LINE
            pic.line.width = Pt(0.75)
        return pic

    def label(self, s: Any, txt: str, x: Emu, y: Emu, w: Emu = Inches(4)) -> None:
        self.text(s, txt.upper(), x, y, w, Inches(0.25), 9.5, PEWTER, bold=True, spacing=1.2)

    # ------------------------------------------------------------------ composite blocks
    def flow(self, s: Any, steps: list[str], x: Emu, y: Emu, w: Emu, h: Emu = Inches(0.78), size: float = 11,
             highlight: int | None = None, vertical: bool = False) -> None:
        n = len(steps)
        if vertical:
            gap = Inches(0.18)
            bh = int((h - gap * (n - 1)) / n)
            for i, st in enumerate(steps):
                yy = y + i * (bh + gap)
                fill = LIME if i == highlight else PAPER
                self.boxtext(s, x, yy, w, bh, st, size, fill, INK, True, None if i == highlight else LINE)
                if i < n - 1:
                    self.arrow(s, x + w // 2, yy + bh, x + w // 2, yy + bh + gap)
            return
        gap = Inches(0.22)
        bw = int((w - gap * (n - 1)) / n)
        for i, st in enumerate(steps):
            xx = x + i * (bw + gap)
            fill = LIME if i == highlight else PAPER
            self.boxtext(s, xx, y, bw, h, st, size, fill, INK, True, None if i == highlight else LINE)
            if i < n - 1:
                self.arrow(s, xx + bw, y + h // 2, xx + bw + gap, y + h // 2)

    def callout(self, s: Any, title: str, body: str, x: Emu, y: Emu, w: Emu, h: Emu, icon: str = "scale") -> None:
        self.box(s, x, y, w, h, TINT, None, 0.14)
        self.icon(s, icon, x + Inches(0.2), y + Inches(0.2), Inches(0.42), "olive", PAPER)
        self.text(s, title, x + Inches(0.75), y + Inches(0.24), w - Inches(0.95), Inches(0.3), 12, OLIVE, bold=True)
        self.text(s, body, x + Inches(0.2), y + Inches(0.75), w - Inches(0.4), h - Inches(0.85), 13.5, INK, line=1.2)

    def point_slide(self, p: dict[str, Any]) -> None:
        s = self.new(p["title"], f"Required point {p['n']} of 8", p["notes"])
        # what we do
        self.text(s, p["what"], MX, Inches(1.5), Inches(7.6), Inches(0.75), 15, GRAPHITE, line=1.18)
        # how it works
        self.label(s, "How it works", MX, Inches(2.42))
        self.flow(s, p["flow"], MX, Inches(2.75), Inches(7.6), Inches(0.95), 12, p.get("highlight"))
        # detail rows under flow
        y = Inches(3.95)
        if p.get("detail"):
            self.label(s, p.get("detail_label", "Inside the engine"), MX, y)
            yy = y + Inches(0.32)
            for icon, head, body in p["detail"]:
                self.icon(s, icon, MX, yy, Inches(0.42))
                self.text(s, head, MX + Inches(0.55), yy + Inches(0.0), Inches(7), Inches(0.28), 12.5, INK, bold=True)
                self.text(s, body, MX + Inches(0.55), yy + Inches(0.28), Inches(7), Inches(0.3), 11.5, GRAPHITE)
                yy += Inches(0.66)
        # right column: data + callout
        rx, rw = Inches(8.55), Inches(4.18)
        card = self.box(s, rx, Inches(1.5), rw, Inches(2.0), PAPER, LINE, 0.14)
        self.label(s, "Data used", rx + Inches(0.22), Inches(1.68))
        end = self.chips(s, p["data"], rx + Inches(0.22), Inches(2.0), rw - Inches(0.4), 10.5)
        card.height = end - Inches(1.5) + Inches(0.22)
        cy = end + Inches(0.42)
        self.callout(s, p["callout"][0], p["callout"][1], rx, cy, rw, Inches(6.85) - cy, p.get("callout_icon", "scale"))


# ====================================================================== slides
def build() -> None:
    d = Deck()

    # 1 — Title ---------------------------------------------------------------------------
    s = d.new("", notes=C.NOTES["title"], header=False)
    d.box(s, Inches(7.55), 0, Inches(5.8), H, TINT, None, 0)
    d.text(s, "HERO HOUSING FINTECH CHALLENGE  ·  PROBLEM STATEMENT 2", MX, Inches(0.9), Inches(7), Inches(0.3), 11, OLIVE, bold=True, spacing=1.5)
    d.text(s, "FinPilot HomeLoan", MX, Inches(1.55), Inches(7), Inches(1.0), 46, INK, bold=True)
    d.text(s, "Explainable, humanless mortgage underwriting for Home Loans and LAP — from application to an audit-ready decision in minutes.",
           MX, Inches(2.65), Inches(6.6), Inches(1.3), 19, GRAPHITE, line=1.2)
    for i, (ic, t) in enumerate([("zap", "Instant approve / reject / refer"), ("scale", "Rules + ML hybrid, every reason cited"),
                                 ("shield-check", "Consent-first, KYC/AML built in")]):
        yy = Inches(4.15 + i * 0.55)
        d.icon(s, ic, MX, yy, Inches(0.4))
        d.text(s, t, MX + Inches(0.55), yy + Inches(0.07), Inches(6), Inches(0.3), 14, INK, bold=True)
    d.text(s, "Team DoubleStack  ·  i-Hack, E-Summit ’26, IIT Bombay", MX, Inches(6.45), Inches(7), Inches(0.3), 13, INK, bold=True)
    d.picture(s, SCREENS / "title_zoom.png", Inches(7.95), Inches(1.0), w=Inches(5.0))
    d.text(s, "Prototype UI · synthetic applicant", Inches(7.95), Inches(6.62), Inches(5), Inches(0.25), 9.5, PEWTER)

    # 2 — Problem -------------------------------------------------------------------------
    s = d.new("A growing book needs underwriting that scales", "The problem", C.NOTES["problem"])
    d.text(s, C.PROBLEM_LEAD, MX, Inches(1.5), Inches(12), Inches(0.6), 15, GRAPHITE)
    for i, (big, small, src) in enumerate(C.PROBLEM_FACTS):
        x = MX + Inches(i * 3.06)
        d.box(s, x, Inches(2.3), Inches(2.88), Inches(2.05), PAPER, LINE, 0.16)
        d.text(s, big, x + Inches(0.22), Inches(2.5), Inches(2.5), Inches(0.7), 26, INK, bold=True)
        d.text(s, small, x + Inches(0.22), Inches(3.2), Inches(2.5), Inches(0.75), 11, GRAPHITE, line=1.15)
        d.text(s, src, x + Inches(0.22), Inches(3.98), Inches(2.5), Inches(0.3), 8.5, PEWTER)
    d.label(s, "Pain points we solve", MX, Inches(4.65))
    for i, (ic, head, body) in enumerate(C.PAINS):
        x = MX + Inches(i * 3.06)
        d.icon(s, ic, x, Inches(5.0), Inches(0.46))
        d.text(s, head, x + Inches(0.58), Inches(5.02), Inches(2.4), Inches(0.3), 12.5, INK, bold=True)
        d.text(s, body, x + Inches(0.58), Inches(5.32), Inches(2.35), Inches(1.3), 10.5, GRAPHITE, line=1.15)

    # 3 — Solution in one picture ----------------------------------------------------------
    s = d.new("One flow from application to an audit-ready decision", "Our solution", C.NOTES["solution"])
    stages = [("database", "Ingest", "Consent · AA · bureau\nKYC · income · property"),
              ("scan-search", "Verify", "Document AI · OCR\ntamper checks"),
              ("fingerprint", "KYC / AML", "PAN · e-KYC · CKYC\nsanctions · PEP"),
              ("calculator", "Assess", "Income & FOIR · AVM\nLTV · fraud graph"),
              ("gauge", "Score", "Calibrated PD\nSHAP reason codes"),
              ("gavel", "Decide", "Policy engine →\napprove / reject / refer"),
              ("file-check-2", "Document", "KFS · sanction letter\naudit ledger")]
    n = len(stages)
    bw, gap = Inches(1.58), Inches(0.17)
    for i, (ic, t, sub) in enumerate(stages):
        x = MX + i * (bw + gap)
        fill = LIME if t == "Decide" else PAPER
        d.box(s, x, Inches(1.75), bw, Inches(2.35), fill, None if t == "Decide" else LINE, 0.16)
        d.icon(s, ic, x + Inches(0.5), Inches(1.95), Inches(0.58), "olive" if t != "Decide" else "ink", PAPER if t == "Decide" else TINT)
        d.text(s, t, x + Inches(0.08), Inches(2.68), bw - Inches(0.16), Inches(0.35), 14, INK, bold=True, align=PP_ALIGN.CENTER)
        d.text(s, sub, x + Inches(0.08), Inches(3.08), bw - Inches(0.16), Inches(0.9), 10, GRAPHITE, align=PP_ALIGN.CENTER)
        if i < n - 1:
            d.arrow(s, x + bw, Inches(2.92), x + bw + gap, Inches(2.92), OLIVE, 1.5)
    # outcomes band
    d.label(s, "Outcome in seconds", MX, Inches(4.45))
    outs = [("Approve", "Straight-through; KFS + sanction letter drafted", LIME),
            ("Approve with conditions", "e.g. reduce to max eligible, add co-applicant", TINT),
            ("Refer", "Exceptions to the right queue with evidence + SLA", PAPER),
            ("Reject", "Written reasons per Fair Practices Code", PAPER)]
    for i, (t, sub, fill) in enumerate(outs):
        x = MX + Inches(i * 3.06)
        d.boxtext(s, x, Inches(4.78), Inches(2.88), Inches(0.95), f"{t}\n{sub}", 13, fill, INK, True, None if fill == LIME else LINE)
    d.text(s, C.SOLUTION_FOOT, MX, Inches(6.05), Inches(12.1), Inches(0.75), 12.5, GRAPHITE, line=1.18)

    # 4–11 — required points -----------------------------------------------------------------
    for p in C.POINTS:
        d.point_slide(p)

    # 12 — Architecture --------------------------------------------------------------------------
    s = d.new("Cloud-native, layered and secure by design", "Architecture", C.NOTES["architecture"])
    layers = [
        ("Channels", ["RM / branch app", "Customer portal", "DSA / partner API", "LOS integration"], PAPER),
        ("API & orchestration", ["API gateway (OAuth2, mTLS)", "Workflow orchestrator (stateful graph)", "Event bus", "Consent manager"], PAPER),
        ("Decision engines", ["Document AI", "KYC / AML", "Income & FOIR", "Property & AVM", "Fraud graph", "Risk model", "Policy engine", "Decision & KFS"], TINT),
        ("Data", ["Case store (PostgreSQL)", "Document vault (encrypted object store)", "Feature store", "Audit ledger (hash-chained)"], PAPER),
    ]
    y = Inches(1.55)
    for name, items, fill in layers:
        d.boxtext(s, MX, y, Inches(1.95), Inches(1.08), name, 12.5, LIME if fill == TINT else FOG, INK, True, None)
        n = len(items)
        x0, wtot = MX + Inches(2.1), Inches(7.85)
        gap = Inches(0.1)
        bw = int((wtot - gap * (n - 1)) / n)
        for i, it in enumerate(items):
            bt = d.boxtext(s, x0 + i * (bw + gap), y, bw, Inches(1.08), it, 9.5 if n > 4 else 11.5, fill, INK, True, LINE)
            bt.text_frame.margin_left = bt.text_frame.margin_right = Inches(0.03)
        y += Inches(1.2)
    # right rail: external sources + governance
    rx = Inches(10.75)
    d.boxtext(s, rx, Inches(1.55), Inches(1.98), Inches(2.28), "External sources\nAA · bureaus · NSDL PAN\nUIDAI · CKYCR · CERSAI\nGSTN · 26AS/AIS\nland records · sanctions", 11.5, PAPER, INK, True, LINE)
    d.boxtext(s, rx, Inches(3.95), Inches(1.98), Inches(2.28), "Governance\nmodel registry · policy repo\ndrift & fairness monitor\nchallenger models\naccess & key vault", 11.5, PAPER, INK, True, LINE)
    d.text(s, C.ARCH_FOOT, MX, Inches(6.38), Inches(12.1), Inches(0.55), 11.5, GRAPHITE, line=1.15)

    # 13 — Prototype UI ------------------------------------------------------------------------
    s = d.new("Prototype UI: what an underwriter actually sees", "Product", C.NOTES["ui"])
    top, avail = Inches(1.5), Inches(4.75)
    big_h = avail
    big_w = int(big_h * 16 / 10)
    d.picture(s, SCREENS / "app_decision.png", MX, top, w=big_w)
    d.boxtext(s, MX + Inches(0.15), top + big_h - Inches(0.5), Inches(5.3), Inches(0.36),
              "Prototype UI · Decision card: reasons, conditions, path to approval", 10.5, PAPER, INK, True, LINE, PP_ALIGN.LEFT, 0.16)
    sm_h = int((avail - Inches(0.2)) / 2)
    sm_w = int(sm_h * 16 / 10)
    rx = W - MX - sm_w
    for i, (f, cap) in enumerate([("fraud_graph.png", "Fraud graph · design mockup"), ("app_audit.png", "Audit trail · hash-chained")]):
        y = top + i * (sm_h + Inches(0.2))
        d.picture(s, SCREENS / f, rx, y, w=sm_w)
        d.boxtext(s, rx + Inches(0.1), y + sm_h - Inches(0.44), Inches(3.4), Inches(0.32), f"Prototype UI · {cap}", 9.5, PAPER, INK, True, LINE, PP_ALIGN.LEFT, 0.16)
    d.text(s, "Working prototype on synthetic applicants: pipeline, case review, copilot, portfolio and model card are live; the fraud graph is the next module (mockup).",
           MX, Inches(6.45), Inches(12.1), Inches(0.45), 11, GRAPHITE)

    # 14 — Impact & KPIs + scalability --------------------------------------------------------------
    s = d.new("Impact for Hero Housing: targets, not promises", "Impact & scalability", C.NOTES["impact"])
    for i, (big, small, basis) in enumerate(C.KPIS):
        x = MX + Inches((i % 4) * 3.06)
        d.box(s, x, Inches(1.5), Inches(2.88), Inches(2.25), LIME if i == 0 else PAPER, None if i == 0 else LINE, 0.16)
        d.text(s, "TARGET", x + Inches(0.22), Inches(1.68), Inches(2.4), Inches(0.25), 9, OLIVE if i else INK, bold=True, spacing=1.2)
        d.text(s, big, x + Inches(0.22), Inches(1.95), Inches(2.5), Inches(0.6), 24, INK, bold=True)
        d.text(s, small, x + Inches(0.22), Inches(2.55), Inches(2.5), Inches(0.45), 11, INK, bold=True, line=1.1)
        d.text(s, basis, x + Inches(0.22), Inches(3.02), Inches(2.5), Inches(0.7), 9.5, GRAPHITE, line=1.12)
    d.label(s, "Scalability (estimates from prototype measurements)", MX, Inches(4.2), Inches(10))
    for i, (big, small) in enumerate(C.SCALE):
        x = MX + Inches(i * 3.06)
        d.box(s, x, Inches(4.5), Inches(2.88), Inches(1.3), PAPER, LINE, 0.16)
        d.text(s, big, x + Inches(0.22), Inches(4.62), Inches(2.5), Inches(0.5), 20, INK, bold=True)
        d.text(s, small, x + Inches(0.22), Inches(5.12), Inches(2.5), Inches(0.6), 10, GRAPHITE, line=1.12)
    d.label(s, "How the pilot will measure it", MX, Inches(5.92), Inches(6))
    d.chips(s, C.MEASURES, MX, Inches(6.2), Inches(12.1), 10, PAPER, 0.06, 0.3)
    d.text(s, C.IMPACT_FOOT, MX, Inches(3.82), Inches(12.1), Inches(0.3), 9.5, PEWTER)

    # 15 — Roadmap, risks & mitigations ------------------------------------------------------------------
    s = d.new("Roadmap: pilot in shadow mode, then scale", "Implementation plan", C.NOTES["roadmap"])
    for i, (phase, when, items) in enumerate(C.ROADMAP):
        x = MX + Inches(i * 3.06)
        d.box(s, x, Inches(1.5), Inches(2.88), Inches(2.55), LIME if i == 0 else PAPER, None if i == 0 else LINE, 0.16)
        d.text(s, when, x + Inches(0.22), Inches(1.65), Inches(2.5), Inches(0.25), 9.5, INK if i == 0 else OLIVE, bold=True, spacing=1.2)
        d.text(s, phase, x + Inches(0.22), Inches(1.92), Inches(2.5), Inches(0.4), 16, INK, bold=True)
        d.text(s, "\n".join("•  " + t for t in items), x + Inches(0.22), Inches(2.42), Inches(2.5), Inches(1.6), 10.5, INK, line=1.2)
    d.label(s, "Risks & mitigations", MX, Inches(4.35))
    for i, (risk, mit) in enumerate(C.RISKS):
        y = Inches(4.68 + i * 0.47)
        d.box(s, MX, y, Inches(12.1), Inches(0.4), PAPER, LINE, 0.1)
        d.text(s, risk, MX + Inches(0.2), y + Inches(0.09), Inches(3.9), Inches(0.28), 11, INK, bold=True)
        d.text(s, mit, MX + Inches(4.2), y + Inches(0.09), Inches(7.8), Inches(0.28), 11, GRAPHITE)

    # 16 — Team & thank you --------------------------------------------------------------------------------
    s = d.new("", notes=C.NOTES["team"], header=False)
    d.box(s, 0, 0, W, H, TINT, None, 0)
    d.text(s, "THANK YOU", MX, Inches(1.2), Inches(8), Inches(0.3), 12, OLIVE, bold=True, spacing=2)
    d.text(s, "Team DoubleStack", MX, Inches(1.6), Inches(8), Inches(0.9), 44, INK, bold=True)
    d.text(s, "B.Tech AI & ML  ·  PCCoE, Pune", MX, Inches(2.6), Inches(8), Inches(0.4), 18, GRAPHITE)
    d.text(s, C.TEAM_LINE, MX, Inches(3.35), Inches(7.2), Inches(1.4), 15, INK, line=1.25)
    for i, (ic, t) in enumerate([("rocket", "Working prototype: 12 synthetic personas, decisions in seconds"),
                                 ("book-open-check", "Every regulation cited — see appendix"),
                                 ("users", "Ready for a shadow-mode pilot on Hero Housing files")]):
        yy = Inches(4.95 + i * 0.52)
        d.icon(s, ic, MX, yy, Inches(0.38), "olive", PAPER)
        d.text(s, t, MX + Inches(0.52), yy + Inches(0.07), Inches(7.5), Inches(0.3), 13, INK, bold=True)
    d.picture(s, SCREENS / "fraud_graph.png", Inches(8.3), Inches(1.4), w=Inches(4.45))
    d.text(s, "Team DoubleStack  |  PS2", MX, Inches(7.1), Inches(4), Inches(0.25), 9.5, PEWTER)
    d.text(s, f"{d.n:02d}", W - MX - Inches(1), Inches(7.1), Inches(1), Inches(0.25), 9.5, PEWTER, align=PP_ALIGN.RIGHT)

    # 17 — Appendix A: sources -------------------------------------------------------------------------------
    s = d.new("Sources", "Appendix A", C.NOTES["sources"])
    half = (len(C.SOURCES) + 1) // 2
    for col, chunk in enumerate((C.SOURCES[:half], C.SOURCES[half:])):
        x = MX + Inches(col * 6.15)
        tb = s.shapes.add_textbox(x, Inches(1.45), Inches(5.95), Inches(5.45))
        tf = tb.text_frame
        tf.word_wrap = True
        for i, (k, label, url) in enumerate(chunk):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(6)
            r = p.add_run()
            r.text = f"[{k}] {label} — "
            r.font.size, r.font.name, r.font.color.rgb = Pt(10), FONT, INK
            r2 = p.add_run()
            r2.text = url
            r2.font.size, r2.font.name, r2.font.color.rgb = Pt(9), FONT, OLIVE
            r2.hyperlink.address = url

    # 18 — Appendix B: compliance matrix ---------------------------------------------------------------------
    s = d.new("Compliance & judging-criteria matrix", "Appendix B", C.NOTES["matrix"])
    rows = C.MATRIX
    tbl = s.shapes.add_table(len(rows) + 1, 3, MX, Inches(1.45), Inches(12.1), Inches(0.3 * (len(rows) + 1))).table
    tbl.columns[0].width, tbl.columns[1].width, tbl.columns[2].width = Inches(3.6), Inches(4.0), Inches(4.5)
    for j, h in enumerate(["Requirement", "Where it is handled", "Evidence / source"]):
        c = tbl.cell(0, j)
        c.fill.solid()
        c.fill.fore_color.rgb = LIME
        c.text = h
    for i, row in enumerate(rows, start=1):
        for j, v in enumerate(row):
            c = tbl.cell(i, j)
            c.fill.solid()
            c.fill.fore_color.rgb = PAPER if i % 2 else FOG
            c.text = v
    for i in range(len(rows) + 1):
        tbl.rows[i].height = Inches(0.34)
        for j in range(3):
            c = tbl.cell(i, j)
            c.margin_top = c.margin_bottom = Inches(0.03)
            for p in c.text_frame.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(10.5 if i else 11)
                    r.font.name = FONT
                    r.font.bold = i == 0
                    r.font.color.rgb = INK

    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.prs.save(str(OUT))
    print(f"wrote {OUT} — {d.n} slides")


if __name__ == "__main__":
    build()
