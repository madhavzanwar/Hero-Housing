"""Run all synthetic personas through the full pipeline and write submission/persona_results.json.

Usage:  cd backend && python scripts/run_personas.py
Prints a persona → outcome table (engine vs expected) used by docs/QA.md and the deck.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.pipeline import run_case  # noqa: E402
from app.store import expected_outcomes, list_personas  # noqa: E402


def main() -> int:
    rows = []
    for p in list_personas():
        files = [(name, (p.path / name).read_bytes()) for name in p.files]
        t0 = time.perf_counter()
        case = run_case(p.form, files, persona_id=p.id)
        wall_ms = int((time.perf_counter() - t0) * 1000)
        accepted = expected_outcomes(p.expected)
        outcome = case.decision.outcome.value
        persona_meta = p.raw.get("persona", {})
        rows.append({
            "id": p.id,
            "title": persona_meta.get("title", p.form.applicant_name),
            "segment": persona_meta.get("segment", ""),
            "product": p.form.product.value,
            "outcome": outcome,
            "expected": accepted,
            "match": outcome in accepted,
            "pd": round(case.risk.pd, 4),
            "grade": case.risk.grade,
            "sanctioned": case.decision.sanctioned_amount,
            "flags": len(case.bundle.flags),
            "rules_failed": [r.rule_id for r in case.decision.rules_fired if r.outcome.value == "FAIL"],
            "ms": wall_ms,
        })
    out = ROOT / "submission" / "persona_results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, indent=2))
    w = max(len(r["title"]) for r in rows) if rows else 10
    print(f"{'id':4} {'persona':{w}} {'engine':24} {'expected':30} ok   PD     ms")
    for r in rows:
        print(f"{r['id']:4} {r['title']:{w}} {r['outcome']:24} {'/'.join(r['expected']):30} "
              f"{'✓' if r['match'] else '✗':4} {r['pd']*100:5.1f}% {r['ms']:5d}")
    ok = sum(r["match"] for r in rows)
    print(f"\n{ok}/{len(rows)} personas match expected outcome")
    return 0 if ok == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
