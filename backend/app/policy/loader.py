"""Policy loader: reads the versioned YAML credit policy and exposes typed helpers.

All engine thresholds come from `policy_v1.yaml`; nothing is hard-coded in engine
modules. `get_policy()` returns a process-wide cached instance.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

POLICY_DIR = Path(__file__).resolve().parent
DEFAULT_POLICY = POLICY_DIR / "policy_v1.yaml"

_LAP_NO_REG_REF = "Internal credit policy - RBI prescribes no regulatory LTV for LAP; prudent HFC practice"


class Policy:
    """Thin wrapper around the policy dict with convenience lookups."""

    def __init__(self, raw: dict[str, Any], path: Path | None = None) -> None:
        self.raw: dict[str, Any] = raw
        self.path = path
        self.version: str = str(raw.get("version", "unknown"))
        self._negative: list[dict[str, Any]] | None = None

    # ----------------------------------------------------------------- generic
    def get(self, dotted: str, default: Any = None) -> Any:
        """`policy.get("banking.max_bounces_6m")`."""
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def section(self, name: str) -> dict[str, Any]:
        value = self.raw.get(name, {})
        return value if isinstance(value, dict) else {}

    def ref(self, key: str | None) -> str:
        """Resolve a reference key (e.g. ``RBI_RW_2020``) to its citation text.
        Unknown keys are returned unchanged so free-text references also work."""
        if not key:
            return ""
        refs = self.section("references")
        return str(refs.get(key, key))

    def rule(self, rule_id: str) -> dict[str, Any]:
        """Catalogue entry {name, category, ref} for a rule id (empty dict if unknown)."""
        entry = self.section("rules").get(rule_id)
        return dict(entry) if isinstance(entry, dict) else {}

    def rule_reference(self, rule_id: str) -> str:
        meta = self.rule(rule_id)
        if rule_id.startswith("LTV-LAP") or rule_id == "ELG-LAP-01":
            return _LAP_NO_REG_REF
        return self.ref(meta.get("ref"))

    # ----------------------------------------------------------------- caps
    def foir_cap(self, income: float) -> tuple[str, float]:
        """FOIR cap for a monthly assessed income: (rule_id, cap)."""
        bands = self.get("eligibility.foir_bands", [])
        for band in bands:
            max_income = band.get("max_income")
            if max_income is None or income <= float(max_income):
                return str(band["id"]), float(band["cap"])
        last = bands[-1]
        return str(last["id"]), float(last["cap"])

    def ltv_cap(self, product: Any, loan_amount: float, property_type: str = "RESIDENTIAL") -> tuple[str, float, str]:
        """LTV cap for a loan: (rule_id, cap, reference text).

        Home loan: RBI slab by loan amount (<= 30L 90%, 30-75L 80%, > 75L 75%; inclusive upper bounds).
        LAP: internal cap by property type.
        """
        prod = getattr(product, "value", product)
        ltv = self.section("ltv")
        if prod == "LAP":
            slab = ltv["LAP"].get(property_type) or ltv["LAP"]["RESIDENTIAL"]
            return str(slab["id"]), float(slab["cap"]), _LAP_NO_REG_REF
        for slab in ltv["HOME_LOAN"]:
            max_loan = slab.get("max_loan")
            if max_loan is None or loan_amount <= float(max_loan):
                return str(slab["id"]), float(slab["cap"]), self.ref(slab.get("ref"))
        slab = ltv["HOME_LOAN"][-1]
        return str(slab["id"]), float(slab["cap"]), self.ref(slab.get("ref"))

    def max_loan_by_ltv(
        self, product: Any, property_value: float, property_type: str = "RESIDENTIAL"
    ) -> tuple[float, str, float]:
        """Largest loan permitted by the LTV grid for a property value: (amount, rule_id, cap).

        For home loans the slabs interact (a loan just above Rs 30L drops to 80%), so we take the
        best of min(slab ceiling, cap x value) across slabs."""
        prod = getattr(product, "value", product)
        if property_value <= 0:
            return 0.0, self.ltv_cap(prod, 0, property_type)[0], 0.0
        if prod == "LAP":
            rid, cap, _ = self.ltv_cap(prod, 0, property_type)
            return cap * property_value, rid, cap
        best: tuple[float, str, float] = (0.0, "", 0.0)
        for slab in self.section("ltv")["HOME_LOAN"]:
            cap = float(slab["cap"])
            ceiling = float(slab["max_loan"]) if slab.get("max_loan") is not None else float("inf")
            amount = min(ceiling, cap * property_value)
            if amount > best[0]:
                best = (amount, str(slab["id"]), cap)
        return best

    # ----------------------------------------------------------------- lists
    def negative_list(self) -> list[dict[str, Any]]:
        if self._negative is None:
            fname = self.get("fraud.negative_list_file", "negative_list.yaml")
            base = self.path.parent if self.path else POLICY_DIR
            fpath = base / str(fname)
            if not fpath.exists():
                fpath = POLICY_DIR / str(fname)
            data = yaml.safe_load(fpath.read_text(encoding="utf-8")) if fpath.exists() else {}
            self._negative = list((data or {}).get("entries", []))
        return self._negative

    def to_dict(self) -> dict[str, Any]:
        return self.raw


def load_policy(path: str | None = None) -> Policy:
    p = Path(path) if path else DEFAULT_POLICY
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    return Policy(raw, p)


@lru_cache(maxsize=1)
def get_policy() -> Policy:
    return load_policy()
