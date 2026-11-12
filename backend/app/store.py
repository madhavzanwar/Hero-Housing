"""In-memory case store with JSON persistence under ``backend/.data`` and persona preloading.

* Cases: ``.data/cases/<case_id>.json`` (CaseDetail JSON — masked PII only).
* Document bytes for the viewer: ``.data/files/<case_id>/<filename>`` + ``index.json``.
* Personas: ``data/personas/<persona_id>/{application.json, expected.json, *.pdf|*.png|*.jpg}``.

``DATA_DIR`` overrides the storage root, ``PERSONAS_DIR`` the persona root.
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import ApplicationForm, CaseDetail, CaseSummary

log = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_DIR = BACKEND_DIR.parent
_SAFE = re.compile(r"[^A-Za-z0-9._-]")
DOC_EXTS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def data_dir() -> Path:
    return Path(os.getenv("DATA_DIR", str(BACKEND_DIR / ".data")))


def personas_dir() -> Path | None:
    env = os.getenv("PERSONAS_DIR")
    candidates = [Path(env)] if env else []
    candidates += [REPO_DIR / "data" / "personas", BACKEND_DIR / "data" / "personas",
                   Path("/app/data/personas")]
    for c in candidates:
        if c.is_dir():
            return c
    return None


def safe_name(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/")) or "file"
    return _SAFE.sub("_", base)[:120]


def guess_mime(filename: str) -> str:
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


# --------------------------------------------------------------------------- personas
@dataclass
class Persona:
    id: str
    path: Path
    form: ApplicationForm
    raw: dict[str, Any]
    expected: dict[str, Any]
    files: list[str]

    def read_files(self) -> list[tuple[str, bytes]]:
        return [(f, (self.path / f).read_bytes()) for f in self.files]

    @property
    def expected_outcomes(self) -> list[str]:
        return expected_outcomes(self.expected)


def expected_outcomes(exp: dict[str, Any]) -> list[str]:
    """Normalise the many shapes an expected.json may take into a list of outcome names."""
    out: list[str] = []
    for key in ("outcome", "expected_outcome", "decision", "acceptable_outcomes", "outcomes",
                "acceptable", "expected"):
        v = exp.get(key)
        if v is None:
            continue
        if isinstance(v, dict):
            v = v.get("outcome") or v.get("decision")
        vals = v if isinstance(v, list) else re.split(r"\s*(?:\bor\b|/|,|\|)\s*", str(v))
        out += [str(x).strip().upper() for x in vals if str(x).strip()]
    return list(dict.fromkeys(out))


def load_persona(pid: str) -> Persona | None:
    root = personas_dir()
    if root is None:
        return None
    p = root / safe_name(pid)
    app_file = p / "application.json"
    if not app_file.is_file():
        return None
    raw = json.loads(app_file.read_text(encoding="utf-8"))
    form_data = raw.get("form") or raw.get("application") or raw
    form = ApplicationForm.model_validate(form_data)
    exp_file = p / "expected.json"
    expected = json.loads(exp_file.read_text(encoding="utf-8")) if exp_file.is_file() else {}
    files = sorted(f.name for f in p.iterdir() if f.is_file() and f.suffix.lower() in DOC_EXTS)
    return Persona(id=p.name, path=p, form=form, raw=raw, expected=expected, files=files)


def list_personas() -> list[Persona]:
    root = personas_dir()
    if root is None:
        return []
    out: list[Persona] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        try:
            per = load_persona(d.name)
        except (ValueError, OSError) as exc:
            log.warning("persona %s unreadable: %s", d.name, exc)
            continue
        if per:
            out.append(per)
    return out


# --------------------------------------------------------------------------- store
@dataclass
class StoredFile:
    doc_id: str
    filename: str
    mime_type: str
    path: Path


class CaseStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or data_dir()
        self._lock = threading.RLock()
        self._cases: dict[str, CaseDetail] = {}
        self._files: dict[str, dict[str, StoredFile]] = {}
        self.preload: dict[str, Any] = {"state": "idle", "done": 0, "total": 0, "errors": []}
        self._preload_thread: threading.Thread | None = None

    # ---- persistence
    @property
    def cases_dir(self) -> Path:
        return self.root / "cases"

    @property
    def files_dir(self) -> Path:
        return self.root / "files"

    def load_from_disk(self) -> int:
        n = 0
        if not self.cases_dir.is_dir():
            return 0
        for fp in sorted(self.cases_dir.glob("*.json")):
            try:
                case = CaseDetail.model_validate_json(fp.read_text(encoding="utf-8"))
            except (ValueError, OSError) as exc:
                log.warning("skipping unreadable case %s: %s", fp.name, exc)
                continue
            with self._lock:
                self._cases[case.id] = case
                self._files[case.id] = self._read_index(case.id)
            n += 1
        return n

    def _read_index(self, case_id: str) -> dict[str, StoredFile]:
        idx = self.files_dir / case_id / "index.json"
        if not idx.is_file():
            return {}
        try:
            items = json.loads(idx.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {}
        return {i["doc_id"]: StoredFile(i["doc_id"], i["filename"], i["mime_type"],
                                        self.files_dir / case_id / i["stored"]) for i in items}

    def save(self, case: CaseDetail) -> None:
        with self._lock:
            self._cases[case.id] = case
        try:
            self.cases_dir.mkdir(parents=True, exist_ok=True)
            tmp = self.cases_dir / f"{case.id}.json.tmp"
            tmp.write_text(case.model_dump_json(), encoding="utf-8")
            tmp.replace(self.cases_dir / f"{case.id}.json")
        except OSError as exc:  # persistence is best-effort; memory is authoritative
            log.warning("could not persist case %s: %s", case.id, exc)

    def put(self, case: CaseDetail, files: list[tuple[str, bytes]]) -> CaseDetail:
        """Store a new case plus its document bytes (keyed by DocumentResult.id)."""
        by_name: dict[str, bytes] = {}
        for name, blob in files:
            by_name.setdefault(name, blob)
            by_name.setdefault(safe_name(name), blob)
        stored: dict[str, StoredFile] = {}
        fdir = self.files_dir / case.id
        index: list[dict[str, str]] = []
        for i, doc in enumerate(case.bundle.documents):
            data: bytes | None = by_name.get(doc.filename) or by_name.get(safe_name(doc.filename))
            if data is None and i < len(files):
                data = files[i][1]
            if data is None:
                continue
            fname = f"{i:02d}_{safe_name(doc.filename)}"
            try:
                fdir.mkdir(parents=True, exist_ok=True)
                (fdir / fname).write_bytes(data)
            except OSError as exc:
                log.warning("could not store %s: %s", fname, exc)
                continue
            mime = doc.mime_type or guess_mime(doc.filename)
            stored[doc.id] = StoredFile(doc.id, doc.filename, mime, fdir / fname)
            index.append({"doc_id": doc.id, "filename": doc.filename, "mime_type": mime, "stored": fname})
        if index:
            (fdir / "index.json").write_text(json.dumps(index), encoding="utf-8")
        with self._lock:
            self._files[case.id] = stored
        self.save(case)
        return case

    # ---- queries
    def get(self, case_id: str) -> CaseDetail | None:
        with self._lock:
            return self._cases.get(case_id)

    def all(self) -> list[CaseDetail]:
        with self._lock:
            return sorted(self._cases.values(), key=lambda c: c.created_at, reverse=True)

    def summaries(self) -> list[CaseSummary]:
        return [summarize(c) for c in self.all()]

    def document(self, case_id: str, doc_id: str) -> StoredFile | None:
        with self._lock:
            return self._files.get(case_id, {}).get(doc_id)

    def by_persona(self, pid: str) -> CaseDetail | None:
        with self._lock:
            matches = [c for c in self._cases.values() if c.persona_id == pid]
        return max(matches, key=lambda c: c.created_at) if matches else None

    def clear(self) -> None:
        import shutil
        with self._lock:
            self._cases.clear()
            self._files.clear()
        for d in (self.cases_dir, self.files_dir):
            shutil.rmtree(d, ignore_errors=True)

    # ---- persona preload
    def preload_personas(self, force: bool = False) -> dict[str, Any]:
        """Run every persona not yet in the store (all of them when ``force``). Thread-safe."""
        from app.pipeline import run_case
        personas = list_personas()
        todo = [p for p in personas if force or self.by_persona(p.id) is None]
        with self._lock:
            self.preload = {"state": "running", "done": 0, "total": len(todo), "errors": [],
                            "started_at": datetime.now(timezone.utc).isoformat()}
        for p in todo:
            try:
                files = p.read_files()
                case = run_case(p.form, files, persona_id=p.id, case_id=f"DEMO-{p.id.upper()}")
                self.put(case, files)
            except Exception as exc:
                log.exception("persona %s failed", p.id)
                with self._lock:
                    self.preload["errors"].append({"persona_id": p.id, "error": repr(exc)[:300]})
            with self._lock:
                self.preload["done"] += 1
        with self._lock:
            self.preload["state"] = "done"
        return dict(self.preload)

    def start_preload(self, force: bool = False) -> bool:
        """Kick off persona preload in a daemon thread (no-op if one is running)."""
        with self._lock:
            if self._preload_thread and self._preload_thread.is_alive():
                return False
            self._preload_thread = threading.Thread(
                target=self.preload_personas, kwargs={"force": force}, name="persona-preload", daemon=True)
            self._preload_thread.start()
            return True

    def wait_preload(self, timeout: float | None = None) -> None:
        t = self._preload_thread
        if t:
            t.join(timeout)


def segment_of(case: CaseDetail) -> str:
    emp = "Salaried" if case.form.employment_type.value == "SALARIED" else "Self-employed"
    prod = "HL" if case.form.product.value == "HOME_LOAN" else "LAP"
    return f"{emp} · {prod}"


def summarize(case: CaseDetail) -> CaseSummary:
    s = case.summary()
    s.segment = segment_of(case)
    return s


_store: CaseStore | None = None
_store_lock = threading.Lock()


def get_store() -> CaseStore:
    global _store
    with _store_lock:
        if _store is None:
            _store = CaseStore()
        return _store


def reset_store(root: Path | None = None) -> CaseStore:
    """Replace the global store (used by tests)."""
    global _store
    with _store_lock:
        _store = CaseStore(root)
        return _store
