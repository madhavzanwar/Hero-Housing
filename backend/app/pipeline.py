"""Single entry point to underwrite one case (used by the API, persona preload and scripts)."""
from __future__ import annotations

from app.agent.graph import run_graph
from app.schemas import ApplicationForm, CaseDetail


def run_case(form: ApplicationForm, files: list[tuple[str, bytes]],
             persona_id: str | None = None, case_id: str | None = None) -> CaseDetail:
    """Underwrite ``form`` + uploaded ``files`` (filename, bytes) through the copilot graph."""
    return run_graph(form, files, persona_id=persona_id, case_id=case_id)
