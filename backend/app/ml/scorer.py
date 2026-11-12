"""PD scoring with plain-language SHAP reasons.

``score(features) -> RiskScore``:
  * LightGBM booster (``artifacts/model.txt``) -> raw log-odds
  * Platt calibration (``artifacts/calibrator.json``: pd = sigmoid(a * raw + b))
  * scorecard transform to 300..900 (650 at PD 5%, 50 points to double the odds of good)
  * grade / band from ``policy.risk.pd_bands``
  * top-5 reasons from exact TreeSHAP contributions (``shap.TreeExplainer``),
    expressed in calibrated log-odds (``+`` increases risk)

If the artifacts are missing or unreadable, a deterministic logistic scorecard
(``_fallback``) with the same output shape is used and ``model_version`` says so.
Artifacts are loaded lazily once and cached (scoring is ~ a few ms).
"""
from __future__ import annotations

import json
import logging
import math
import threading
import warnings
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import yaml

from app.ml.features import DEFAULTS, FEATURE_DIRECTION, FEATURE_LABELS, FEATURES, display_value
from app.schemas import RiskScore, ShapReason

log = logging.getLogger(__name__)

ARTIFACT_DIR = Path(__file__).resolve().parent / "artifacts"
POLICY_PATH = Path(__file__).resolve().parents[1] / "policy" / "policy_v1.yaml"

PD_MIN, PD_MAX = 0.0005, 0.9995
SCORE_BASE, SCORE_BASE_ODDS, SCORE_PDO = 650.0, 19.0, 50.0  # 650 <-> odds 19:1 (PD 5%), 50 pts doubles odds
TOP_REASONS = 5

FALLBACK_VERSION = "fallback-logistic-scorecard-v1"

_lock = threading.Lock()


# --------------------------------------------------------------------------- policy
@lru_cache(maxsize=1)
def _pd_bands() -> list[dict[str, Any]]:
    raw: dict[str, Any] | None = None
    try:  # prefer the engine's loader if present
        from app.policy.loader import get_policy  # type: ignore[import-not-found,unused-ignore]

        raw = getattr(get_policy(), "raw", None)
    except Exception:
        raw = None
    if not isinstance(raw, dict):
        with open(POLICY_PATH, encoding="utf-8") as fh:
            raw = yaml.safe_load(fh)
    bands = sorted(raw["risk"]["pd_bands"], key=lambda b: float(b["max_pd"]))
    return [dict(b) for b in bands]


def grade_for(pd: float) -> tuple[str, str]:
    bands = _pd_bands()
    for b in bands:
        if pd <= float(b["max_pd"]):
            return str(b["grade"]), str(b["band"])
    return str(bands[-1]["grade"]), str(bands[-1]["band"])


def pd_to_score(pd: float) -> int:
    odds_good = (1.0 - pd) / pd
    s = SCORE_BASE + SCORE_PDO * math.log2(odds_good / SCORE_BASE_ODDS)
    return round(min(900.0, max(300.0, s)))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


# --------------------------------------------------------------------------- artifacts
class _Model:
    def __init__(self, booster: Any, a: float, b: float, version: str, explainer: Any, features: list[str]):
        self.booster = booster
        self.a = a
        self.b = b
        self.version = version
        self.explainer = explainer
        self.features = features

    def contributions(self, x: np.ndarray) -> tuple[np.ndarray, float]:
        """Return (per-feature SHAP log-odds, expected raw log-odds)."""
        if self.explainer is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                sv = self.explainer.shap_values(x)
            if isinstance(sv, list):  # older shap returns [neg, pos] for binary
                sv = sv[-1]
            ev = self.explainer.expected_value
            ev = float(np.ravel(ev)[-1])
            return np.asarray(sv, dtype=float)[0], ev
        contrib = self.booster.predict(x, pred_contrib=True)[0]  # same TreeSHAP, native
        return np.asarray(contrib[:-1], dtype=float), float(contrib[-1])


_state: dict[str, Any] = {}


def _load() -> _Model | None:
    if "model" in _state:
        return _state["model"]
    with _lock:
        if "model" in _state:
            return _state["model"]
        model: _Model | None = None
        try:
            import lightgbm as lgb

            cal = json.loads((ARTIFACT_DIR / "calibrator.json").read_text(encoding="utf-8"))
            booster = lgb.Booster(model_file=str(ARTIFACT_DIR / "model.txt"))
            feats = list(cal.get("features", FEATURES))
            if feats != FEATURES:
                raise ValueError("artifact feature list does not match app.ml.features.FEATURES")
            explainer = None
            try:
                import shap

                explainer = shap.TreeExplainer(booster)
            except Exception as exc:
                log.warning("shap unavailable (%s); using LightGBM pred_contrib TreeSHAP", exc)
            model = _Model(booster, float(cal["a"]), float(cal["b"]), str(cal["model_version"]), explainer, feats)
        except Exception as exc:
            log.warning("PD model artifacts unavailable (%s); using fallback scorecard", exc)
            model = None
        _state["model"] = model
        return model


def warmup() -> bool:
    """Load artifacts (and import lightgbm/shap) ahead of the first request. True if the model loaded."""
    model = _load()
    if model is not None:
        score({})
    return model is not None


def reset_cache() -> None:
    """Forget loaded artifacts (tests / after retraining)."""
    with _lock:
        _state.clear()
    _metrics.cache_clear()


@lru_cache(maxsize=1)
def _metrics() -> dict[str, Any]:
    try:
        return json.loads((ARTIFACT_DIR / "metrics.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


# --------------------------------------------------------------------------- fallback scorecard
# Hand-set logistic scorecard mirroring the documented risk drivers. Each term is
# expressed relative to a reference "typical" applicant so contributions read
# directly as reasons. The intercept was fitted once on a seeded synthetic sample
# (seed 7, 30k rows; slope 0.97 ~ 1) so the fallback is calibrated to the same ~4%
# portfolio default rate: the reference applicant scores PD ~1%. Fallback AUC ~0.85.
_REF: dict[str, float] = {
    "bureau_score": 745, "foir": 0.38, "ltv": 0.65, "monthly_income": 100_000, "loan_to_income": 2.5,
    "existing_emi_to_income": 0.05, "bounces_6m": 0, "amb_to_emi": 2.0, "income_regularity": 0.89,
    "cash_deposit_share": 0.07, "high_risk_spend_share": 0.0, "years_in_job": 5.0, "age": 38,
    "tenure_months": 240, "is_self_employed": 0, "is_lap": 0, "has_co_applicant": 0, "city_tier": 2,
}
_FALLBACK_INTERCEPT = -4.58


def _fb_term(f: str, v: float) -> float:
    if f == "bureau_score":
        return 0.02 * (720 - v)
    if f == "foir":
        return 1.0 * v + 4 * max(v - 0.45, 0) + 6 * max(v - 0.65, 0)
    if f == "ltv":
        return 2.5 * v + 4 * max(v - 0.85, 0)
    if f == "monthly_income":
        return -0.2 * math.log(max(v, 1.0))
    if f == "loan_to_income":
        return 0.15 * math.log(max(v, 0.2))
    if f == "bounces_6m":
        return 0.35 * min(v, 5)
    if f == "amb_to_emi":
        return -0.35 * math.log(min(max(v, 0.05), 30))
    if f == "income_regularity":
        return -2.0 * v
    if f == "cash_deposit_share":
        return 1.5 * v
    if f == "high_risk_spend_share":
        return 6.0 * v
    if f == "years_in_job":
        return -0.04 * min(v, 15)
    if f == "age":
        return 0.03 * max(25 - v, 0) + 0.04 * max(v - 50, 0)
    if f in ("is_self_employed", "is_lap"):
        return 0.25 * v
    if f == "has_co_applicant":
        return -0.25 * v
    if f == "city_tier":
        return 0.15 * v
    return 0.0  # existing_emi_to_income, tenure_months act through FOIR / LTI


def _fallback(x: dict[str, float]) -> tuple[float, np.ndarray, float]:
    contrib = np.array([_fb_term(f, x[f]) - _fb_term(f, _REF[f]) for f in FEATURES])
    logit = _FALLBACK_INTERCEPT + float(contrib.sum())
    return logit, contrib, _FALLBACK_INTERCEPT


# --------------------------------------------------------------------------- reasons
_NOUN: dict[str, str] = {
    "bureau_score": "credit bureau score",
    "foir": "fixed-obligation-to-income ratio",
    "ltv": "loan-to-value ratio",
    "monthly_income": "assessed monthly income",
    "loan_to_income": "loan size relative to income",
    "existing_emi_to_income": "existing EMI burden",
    "bounces_6m": "cheque/NACH bounces in the last 6 months",
    "amb_to_emi": "average bank balance relative to the proposed EMI",
    "income_regularity": "regularity of income credits",
    "cash_deposit_share": "share of cash deposits in bank credits",
    "high_risk_spend_share": "spend on betting/crypto merchants",
    "years_in_job": "job / business vintage",
    "age": "applicant age",
    "tenure_months": "loan tenure",
    "city_tier": "city tier of the property",
}
_HIGH_LOW: dict[str, tuple[str, str]] = {
    "bureau_score": ("Strong", "Weak"),
    "monthly_income": ("High", "Modest"),
    "amb_to_emi": ("Healthy", "Thin"),
    "income_regularity": ("High", "Low"),
    "years_in_job": ("Long", "Short"),
    "city_tier": ("Smaller-city", "Metro"),
}


def reason_text(feature: str, value: float, impact: float) -> str:
    up = impact > 0
    verb = "increased risk" if up else "reduced risk"
    disp = display_value(feature, value)
    if feature == "is_self_employed":
        return f"{'Self-employed' if value >= 0.5 else 'Salaried'} income profile {verb}"
    if feature == "is_lap":
        return f"{'Loan against property' if value >= 0.5 else 'Home-loan'} product {verb}"
    if feature == "has_co_applicant":
        return f"{'Earning co-applicant' if value >= 0.5 else 'No earning co-applicant'} {verb}"
    if feature in ("bounces_6m", "high_risk_spend_share") and value <= 0:
        return f"No {_NOUN[feature]} {verb}"
    if feature == "city_tier":
        return f"Tier-{value:.0f} city location {verb}"
    noun = _NOUN.get(feature, FEATURE_LABELS.get(feature, feature).lower())
    direction = FEATURE_DIRECTION.get(feature, 0)
    if direction == 0:
        return f"{noun[0].upper()}{noun[1:]} ({disp}) {verb}"
    value_is_high = up == (direction > 0)
    hi, lo = _HIGH_LOW.get(feature, ("High", "Low"))
    return f"{hi if value_is_high else lo} {noun} ({disp}) {verb}"


def _reasons(x: dict[str, float], contrib: np.ndarray) -> list[ShapReason]:
    order = np.argsort(-np.abs(contrib))
    out: list[ShapReason] = []
    for i in order[:TOP_REASONS]:
        imp = float(contrib[i])
        if abs(imp) < 1e-3:
            continue
        f = FEATURES[int(i)]
        out.append(ShapReason(
            feature=f, label=FEATURE_LABELS[f], value=display_value(f, x[f]),
            impact=round(imp, 4), text=reason_text(f, x[f], imp),
        ))
    return out


# --------------------------------------------------------------------------- public API
def _vector(features: dict[str, Any]) -> dict[str, float]:
    x: dict[str, float] = {}
    for f in FEATURES:
        v = features.get(f)
        try:
            fv = float(v) if v is not None else float("nan")
        except (TypeError, ValueError):
            fv = float("nan")
        if not math.isfinite(fv):
            fv = DEFAULTS.get(f, _REF[f])
        x[f] = fv
    return x


def score(features: dict[str, Any]) -> RiskScore:
    """Score one case's feature dict (see ``app.ml.features.build_features``)."""
    x = _vector(features)
    model = _load()
    if model is not None:
        arr = np.array([[x[f] for f in FEATURES]], dtype=float)
        raw = float(model.booster.predict(arr, raw_score=True)[0])
        contrib, ev = model.contributions(arr)
        logit = model.a * raw + model.b
        contrib = contrib * model.a           # into calibrated log-odds space
        base = model.a * ev + model.b
        version = model.version
    else:
        logit, contrib, base = _fallback(x)
        version = FALLBACK_VERSION
    pd = min(PD_MAX, max(PD_MIN, _sigmoid(logit)))
    grade, band = grade_for(pd)
    return RiskScore(
        pd=round(pd, 5), score=pd_to_score(pd), grade=grade, band=band,  # type: ignore[arg-type]
        reasons=_reasons(x, contrib), base_value=round(base, 4), model_version=version,
        features={k: round(v, 4) for k, v in x.items()},
    )


def model_info() -> dict[str, Any]:
    """Model metadata + evaluation metrics for the model-card endpoint / UI."""
    model = _load()
    return {
        "model_version": model.version if model else FALLBACK_VERSION,
        "status": "lightgbm+platt" if model else "fallback-scorecard",
        "explainer": ("shap.TreeExplainer" if model.explainer is not None else "lightgbm.pred_contrib")
        if model else "logistic contributions",
        "features": FEATURES,
        "feature_labels": FEATURE_LABELS,
        "pd_bands": _pd_bands(),
        "score_scale": {"min": 300, "max": 900, "base_score": SCORE_BASE, "base_odds_good": SCORE_BASE_ODDS,
                        "points_to_double_odds": SCORE_PDO},
        "training_data": "SYNTHETIC Indian mortgage borrower dataset (app/ml/synthetic.py); "
                         "method benchmarked on public UCI/OpenML credit datasets",
        "metrics": _metrics(),
    }
