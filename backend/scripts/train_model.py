# ruff: noqa: N803, N806  (X / X_tr follow the scikit-learn naming convention)
"""Train, calibrate, evaluate and fairness-audit the FinPilot HomeLoan PD model.

Run from backend/ (any cwd works):
    python scripts/train_model.py            # full run incl. public benchmark download (~10 s)
    python scripts/train_model.py --no-benchmark

Outputs
    backend/app/ml/artifacts/model.txt        LightGBM booster (text format)
    backend/app/ml/artifacts/calibrator.json  Platt parameters (+ isotonic table for reference)
    backend/app/ml/artifacts/metrics.json     all metrics reported in docs/MODEL_CARD.md
    docs/img/model_*.png                      ROC, calibration, SHAP importance, fairness plots

Data
    * Production model: SYNTHETIC Indian mortgage borrowers (backend/app/ml/synthetic.py),
      60,000 rows, seed 42. Not real borrower data.
    * External benchmark of the *method* (same LightGBM + Platt recipe): public datasets
      fetched without authentication from OpenML -
        - id 42477 "default-of-credit-card-clients" (UCI Taiwan, Yeh & Lien 2009, 30,000 rows)
        - id 31 "credit-g" (Statlog German credit, 1,000 rows)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[1]
ROOT = BACKEND.parent
sys.path.insert(0, str(BACKEND))

import lightgbm as lgb  # noqa: E402
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import shap  # noqa: E402
from fairlearn.metrics import (  # noqa: E402
    MetricFrame,
    demographic_parity_difference,
    equalized_odds_difference,
    false_positive_rate,
    selection_rate,
    true_positive_rate,
)
from sklearn.isotonic import IsotonicRegression  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score, roc_curve  # noqa: E402
from sklearn.model_selection import StratifiedKFold, train_test_split  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from app.ml import scorer  # noqa: E402
from app.ml.features import FEATURE_DIRECTION, FEATURE_LABELS, FEATURES  # noqa: E402
from app.ml.synthetic import generate  # noqa: E402

SEED = 42
ART = BACKEND / "app" / "ml" / "artifacts"
IMG = ROOT / "docs" / "img"
BLUE, ORANGE, INK, MUTED, GRID = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df"

PARAMS: dict[str, Any] = {
    "objective": "binary",
    "learning_rate": 0.02,
    "num_leaves": 7,
    "min_data_in_leaf": 150,
    "feature_fraction": 0.85,
    "bagging_fraction": 0.85,
    "bagging_freq": 1,
    "lambda_l2": 2.0,
    "seed": SEED,
    "deterministic": True,
    "force_row_wise": True,
    "num_threads": 1,
    "verbosity": -1,
}


# --------------------------------------------------------------------------- metrics helpers
def ks_stat(y: np.ndarray, p: np.ndarray) -> float:
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def raw_pred(bst: lgb.Booster, x: Any) -> np.ndarray:
    return np.asarray(bst.predict(x, raw_score=True), dtype=float)


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def fit_platt(raw: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    lr = LogisticRegression(C=1e6, max_iter=1000)
    lr.fit(raw.reshape(-1, 1), y)
    return float(lr.coef_[0, 0]), float(lr.intercept_[0])


def core_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    auc = roc_auc_score(y, p)
    return {
        "auc": round(float(auc), 4),
        "gini": round(float(2 * auc - 1), 4),
        "ks": round(ks_stat(y, p), 4),
        "brier": round(float(brier_score_loss(y, p)), 5),
        "log_loss": round(float(log_loss(y, np.clip(p, 1e-6, 1 - 1e-6))), 5),
        "default_rate": round(float(np.mean(y)), 4),
        "mean_pd": round(float(np.mean(p)), 4),
        "n": len(y),
    }


def calibration_table(y: np.ndarray, p: np.ndarray, bins: int = 10) -> list[dict[str, float]]:
    order = np.argsort(p)
    out = []
    for i, idx in enumerate(np.array_split(order, bins)):
        out.append({
            "decile": i + 1,
            "n": len(idx),
            "mean_pd": round(float(p[idx].mean()), 5),
            "observed_default_rate": round(float(y[idx].mean()), 5),
            "min_pd": round(float(p[idx].min()), 5),
            "max_pd": round(float(p[idx].max()), 5),
        })
    return out


def ece(table: list[dict[str, float]]) -> float:
    n = sum(r["n"] for r in table)
    return round(sum(r["n"] * abs(r["mean_pd"] - r["observed_default_rate"]) for r in table) / n, 5)


def train_lgb(X_tr: pd.DataFrame, y_tr: np.ndarray, X_va: pd.DataFrame, y_va: np.ndarray,
              monotone: list[int] | None = None, rounds: int = 2000) -> lgb.Booster:
    params = dict(PARAMS)
    if monotone is not None:
        params["monotone_constraints"] = monotone
        params["monotone_constraints_method"] = "advanced"
    dtr = lgb.Dataset(X_tr, y_tr, free_raw_data=False)
    dva = lgb.Dataset(X_va, y_va, reference=dtr)
    return lgb.train(params, dtr, num_boost_round=rounds, valid_sets=[dva],
                     callbacks=[lgb.early_stopping(100, verbose=False)])


# --------------------------------------------------------------------------- benchmark
def _bench_one(X: pd.DataFrame, y: np.ndarray, sensitive: pd.Series | None = None) -> dict[str, Any]:
    X_tmp, X_te, y_tmp, y_te = train_test_split(X, y, test_size=0.2, stratify=y, random_state=SEED)
    X_tr, X_ca, y_tr, y_ca = train_test_split(X_tmp, y_tmp, test_size=0.25, stratify=y_tmp, random_state=SEED)
    X_fit, X_es, y_fit, y_es = train_test_split(X_tr, y_tr, test_size=0.15, stratify=y_tr, random_state=SEED)
    bst = train_lgb(X_fit, y_fit, X_es, y_es)
    a, b = fit_platt(raw_pred(bst, X_ca), y_ca)
    p = sigmoid(a * raw_pred(bst, X_te) + b)
    m: dict[str, Any] = core_metrics(y_te, p)
    m["n_total"] = len(y)
    m["best_iteration"] = int(bst.best_iteration)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr.fit(pd.get_dummies(X_tr).astype(float), y_tr)
    Xte_d = pd.get_dummies(X_te).reindex(columns=pd.get_dummies(X_tr).columns, fill_value=0).astype(float)
    m["logistic_baseline_auc"] = round(float(roc_auc_score(y_te, lr.predict_proba(Xte_d)[:, 1])), 4)
    if sensitive is not None:
        s_te = sensitive.loc[X_te.index]
        thr = float(np.quantile(p, 0.8))  # approve the 80% lowest-PD applicants
        approved = (p < thr).astype(int)
        good = 1 - y_te
        m["fairness_sex"] = {
            "approve_rule": "approve lowest-PD 80% of test applicants",
            "selection_rate": {str(k): round(float(v), 4) for k, v in
                               MetricFrame(metrics=selection_rate, y_true=good, y_pred=approved,
                                           sensitive_features=s_te).by_group.items()},
            "demographic_parity_difference": round(float(demographic_parity_difference(
                good, approved, sensitive_features=s_te)), 4),
            "equalized_odds_difference": round(float(equalized_odds_difference(
                good, approved, sensitive_features=s_te)), 4),
        }
    return m


def run_benchmark() -> dict[str, Any]:
    from sklearn.datasets import fetch_openml

    out: dict[str, Any] = {}
    try:
        d = fetch_openml(data_id=42477, as_frame=True, parser="liac-arff")
        df = d.frame.copy()
        y = df.pop("y").astype(int).to_numpy()
        df = df.astype(float)
        sex = df["x2"].map({1.0: "male", 2.0: "female"})
        res = _bench_one(df, y, sensitive=sex)
        res.update({"source": "OpenML 42477 = UCI 'default of credit card clients' (Taiwan, 2005; Yeh & Lien 2009)",
                    "target": "default payment next month",
                    "note": "Credit-card data, not mortgages: benchmarks the method only. "
                            "Literature AUC on this set is typically 0.77-0.79."})
        out["uci_taiwan_credit_card_default"] = res
        print(f"[benchmark] UCI Taiwan  AUC={res['auc']} KS={res['ks']} Brier={res['brier']}")
    except Exception as exc:
        out["uci_taiwan_credit_card_default"] = {"error": f"download/eval failed: {exc}"}
        print("[benchmark] UCI Taiwan failed:", exc)
    try:
        d = fetch_openml(data_id=31, as_frame=True, parser="liac-arff")
        df = d.frame.copy()
        y = (df.pop("class").astype(str) == "bad").astype(int).to_numpy()
        for c in df.columns:
            if str(df[c].dtype) == "category" or df[c].dtype == object:
                df[c] = df[c].astype("category")
        aucs, kss = [], []
        skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
        p_small = dict(PARAMS, num_leaves=7, min_data_in_leaf=20, learning_rate=0.05)
        for tr, te in skf.split(df, y):
            bst = lgb.train(p_small, lgb.Dataset(df.iloc[tr], y[tr]), num_boost_round=200)
            p = np.asarray(bst.predict(df.iloc[te]), dtype=float)
            aucs.append(roc_auc_score(y[te], p))
            kss.append(ks_stat(y[te], p))
        out["german_credit_g"] = {
            "source": "OpenML 31 = Statlog German credit (UCI, Hofmann 1994)",
            "n_total": len(y), "default_rate": round(float(y.mean()), 4),
            "cv": "5-fold stratified, 200 rounds, uncalibrated",
            "auc_mean": round(float(np.mean(aucs)), 4), "auc_std": round(float(np.std(aucs)), 4),
            "ks_mean": round(float(np.mean(kss)), 4),
            "note": "Small (1,000 rows); literature AUC typically 0.75-0.80.",
        }
        print(f"[benchmark] German credit-g AUC={np.mean(aucs):.4f}±{np.std(aucs):.4f}")
    except Exception as exc:
        out["german_credit_g"] = {"error": f"download/eval failed: {exc}"}
        print("[benchmark] credit-g failed:", exc)
    return out


# --------------------------------------------------------------------------- fairness
def age_band(age: pd.Series) -> pd.Series:
    return pd.cut(age, bins=[0, 30, 45, 200], labels=["<30", "30-45", "45+"], right=False).astype(str)


def fairness(y: np.ndarray, p: np.ndarray, groups: dict[str, pd.Series], approve_pd: float) -> dict[str, Any]:
    good = 1 - y
    approved = (p < approve_pd).astype(int)
    out: dict[str, Any] = {
        "approve_rule": f"model-only approve if calibrated PD < {approve_pd:.0%} (grades A-B)",
        "framing": "positive label = good borrower (no default); TPR = approval rate among good borrowers "
                   "(equal opportunity), FPR = approval rate among borrowers who defaulted",
    }
    for name, s in groups.items():
        mf = MetricFrame(
            metrics={"selection_rate": selection_rate, "tpr": true_positive_rate, "fpr": false_positive_rate},
            y_true=good, y_pred=approved, sensitive_features=s.to_numpy(),
        )
        bg = mf.by_group
        cal = pd.DataFrame({"g": s.to_numpy(), "y": y, "p": p}).groupby("g").agg(
            n=("y", "size"), observed_default_rate=("y", "mean"), mean_pd=("p", "mean"))
        auc_g = {str(g): round(float(roc_auc_score(y[s.to_numpy() == g], p[s.to_numpy() == g])), 4)
                 for g in cal.index}
        out[name] = {
            "by_group": {
                str(g): {
                    "n": int(cal.loc[g, "n"]),
                    "selection_rate": round(float(bg.loc[g, "selection_rate"]), 4),
                    "tpr": round(float(bg.loc[g, "tpr"]), 4),
                    "fpr": round(float(bg.loc[g, "fpr"]), 4),
                    "observed_default_rate": round(float(cal.loc[g, "observed_default_rate"]), 4),
                    "mean_pd": round(float(cal.loc[g, "mean_pd"]), 4),
                    "auc": auc_g[str(g)],
                } for g in cal.index
            },
            "demographic_parity_difference": round(float(demographic_parity_difference(
                good, approved, sensitive_features=s.to_numpy())), 4),
            "demographic_parity_ratio": round(float(bg["selection_rate"].min() / bg["selection_rate"].max()), 4),
            "equalized_odds_difference": round(float(equalized_odds_difference(
                good, approved, sensitive_features=s.to_numpy())), 4),
        }
    return out


# --------------------------------------------------------------------------- plots
def _style(ax: Any) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def plots(y: np.ndarray, p: np.ndarray, cal: list[dict[str, float]], imp: list[dict[str, Any]],
          fair: dict[str, Any], auc: float) -> list[str]:
    IMG.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 10, "text.color": INK, "axes.labelcolor": MUTED})
    files = []

    fpr, tpr, _ = roc_curve(y, p)
    fig, ax = plt.subplots(figsize=(5, 4.2), dpi=110)
    ax.plot(fpr, tpr, color=BLUE, lw=2, label=f"LightGBM + Platt (AUC {auc:.3f})")
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1, ls="--", label="Random")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC - synthetic holdout test set", loc="left", fontsize=11)
    ax.legend(frameon=False, loc="lower right", fontsize=9)
    _style(ax)
    fig.tight_layout()
    fig.savefig(IMG / "model_roc.png")
    plt.close(fig)
    files.append("docs/img/model_roc.png")

    fig, ax = plt.subplots(figsize=(5, 4.2), dpi=110)
    mp = [r["mean_pd"] for r in cal]
    ob = [r["observed_default_rate"] for r in cal]
    hi = max(max(mp), max(ob)) * 1.08
    ax.plot([0, hi], [0, hi], color=MUTED, lw=1, ls="--", label="Perfect calibration")
    ax.plot(mp, ob, color=BLUE, lw=2, marker="o", ms=6, label="Model (deciles)")
    ax.set_xlabel("Mean predicted PD")
    ax.set_ylabel("Observed default rate")
    ax.set_title("Calibration by PD decile", loc="left", fontsize=11)
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    _style(ax)
    fig.tight_layout()
    fig.savefig(IMG / "model_calibration.png")
    plt.close(fig)
    files.append("docs/img/model_calibration.png")

    top = imp[:12][::-1]
    fig, ax = plt.subplots(figsize=(6.4, 4.6), dpi=110)
    ax.barh([t["label"] for t in top], [t["mean_abs_shap"] for t in top], color=BLUE, height=0.6)
    for i, t in enumerate(top):
        ax.text(t["mean_abs_shap"], i, f" {t['mean_abs_shap']:.3f}", va="center", fontsize=8, color=MUTED)
    ax.set_xlabel("Mean |SHAP| (log-odds)")
    ax.set_title("Global feature importance (SHAP)", loc="left", fontsize=11)
    _style(ax)
    ax.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(IMG / "model_shap_importance.png")
    plt.close(fig)
    files.append("docs/img/model_shap_importance.png")

    fig, axes = plt.subplots(1, 2, figsize=(8, 3.6), dpi=110, sharey=True)
    for ax, key, title in ((axes[0], "gender", "Gender (not a model feature)"), (axes[1], "age_band", "Age band")):
        bg = fair[key]["by_group"]
        pref = ["<30", "30-45", "45+", "F", "M"]
        groups = sorted(bg, key=lambda g: pref.index(g) if g in pref else 99)
        x = np.arange(len(groups))
        w = 0.38
        sel = [bg[g]["selection_rate"] for g in groups]
        tp = [bg[g]["tpr"] for g in groups]
        ax.bar(x - w / 2 - 0.01, sel, w, color=BLUE, label="Approval rate (all)")
        ax.bar(x + w / 2 + 0.01, tp, w, color=ORANGE, label="Approval rate (good borrowers)")
        for xi, v in zip(x - w / 2 - 0.01, sel, strict=False):
            ax.text(xi, v + 0.01, f"{v:.0%}", ha="center", fontsize=8, color=MUTED)
        for xi, v in zip(x + w / 2 + 0.01, tp, strict=False):
            ax.text(xi, v + 0.01, f"{v:.0%}", ha="center", fontsize=8, color=MUTED)
        ax.set_xticks(x, groups)
        ax.set_ylim(0, 1.08)
        ax.set_title(f"{title}\nDP diff {fair[key]['demographic_parity_difference']:.3f} · "
                     f"EO diff {fair[key]['equalized_odds_difference']:.3f}", loc="left", fontsize=10)
        _style(ax)
        ax.grid(axis="x", visible=False)
    axes[0].legend(frameon=False, loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(IMG / "model_fairness.png")
    plt.close(fig)
    files.append("docs/img/model_fairness.png")
    return files


# --------------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=int, default=60_000)
    ap.add_argument("--no-benchmark", action="store_true")
    args = ap.parse_args()
    warnings.filterwarnings("ignore")
    np.random.seed(SEED)

    df = generate(n=args.rows, seed=SEED)
    X, y = df[FEATURES], df["default"].to_numpy()
    idx = np.arange(len(df))
    i_tmp, i_te = train_test_split(idx, test_size=0.2, stratify=y, random_state=SEED)
    i_tr, i_ca = train_test_split(i_tmp, test_size=0.25, stratify=y[i_tmp], random_state=SEED)
    i_fit, i_es = train_test_split(i_tr, test_size=0.15, stratify=y[i_tr], random_state=SEED)
    print(f"[data] synthetic rows={len(df)} default_rate={y.mean():.4f} "
          f"train={len(i_fit)} early_stop={len(i_es)} calib={len(i_ca)} test={len(i_te)}")

    monotone = [FEATURE_DIRECTION[f] for f in FEATURES]
    bst = train_lgb(X.iloc[i_fit], y[i_fit], X.iloc[i_es], y[i_es], monotone=monotone)
    print(f"[train] best_iteration={bst.best_iteration}")

    raw_ca = raw_pred(bst, X.iloc[i_ca])
    raw_te = raw_pred(bst, X.iloc[i_te])
    a, b = fit_platt(raw_ca, y[i_ca])
    p_te = sigmoid(a * raw_te + b)
    p_uncal = sigmoid(raw_te)
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(sigmoid(raw_ca), y[i_ca])
    p_iso = iso.predict(p_uncal)

    m = core_metrics(y[i_te], p_te)
    cal = calibration_table(y[i_te], p_te)
    print(f"[test] AUC={m['auc']} Gini={m['gini']} KS={m['ks']} Brier={m['brier']} ECE={ece(cal)}")

    # baselines on the same split
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr.fit(X.iloc[i_tr], y[i_tr])
    lr_auc = roc_auc_score(y[i_te], lr.predict_proba(X.iloc[i_te])[:, 1])
    fb_logit = np.array([scorer._fallback({f: float(r[f]) for f in FEATURES})[0]
                         for r in X.iloc[i_te].to_dict("records")])
    fb_p = sigmoid(fb_logit)
    fb = {"auc": round(float(roc_auc_score(y[i_te], fb_p)), 4), "brier": round(float(brier_score_loss(y[i_te], fb_p)), 5),
          "mean_pd": round(float(fb_p.mean()), 4)}
    oracle_auc = roc_auc_score(y[i_te], df["true_pd"].to_numpy()[i_te])

    # PD bands
    bands = scorer._pd_bands()
    band_rows = []
    lo = 0.0
    for bd in bands:
        mask = (p_te > lo) & (p_te <= float(bd["max_pd"])) if lo > 0 else p_te <= float(bd["max_pd"])
        band_rows.append({
            "grade": bd["grade"], "band": bd["band"], "pd_range": f"{lo:.0%}-{float(bd['max_pd']):.0%}",
            "share": round(float(mask.mean()), 4), "n": int(mask.sum()),
            "observed_default_rate": round(float(y[i_te][mask].mean()), 4) if mask.any() else None,
            "mean_pd": round(float(p_te[mask].mean()), 4) if mask.any() else None,
            "policy_action": bd.get("action"),
        })
        lo = float(bd["max_pd"])

    # SHAP global importance on a test sample
    rng = np.random.default_rng(SEED)
    sample = rng.choice(i_te, size=min(3000, len(i_te)), replace=False)
    sv = shap.TreeExplainer(bst).shap_values(X.iloc[sample])
    if isinstance(sv, list):
        sv = sv[-1]
    mean_abs = np.abs(np.asarray(sv)).mean(axis=0) * a
    imp: list[dict[str, Any]] = sorted(
        ({"feature": f, "label": FEATURE_LABELS[f], "mean_abs_shap": round(float(v), 4)}
         for f, v in zip(FEATURES, mean_abs, strict=False)),
        key=lambda r: -float(r["mean_abs_shap"]),
    )

    # fairness on the test set
    approve_pd = float(next(bd["max_pd"] for bd in bands if bd["grade"] == "B"))
    test = df.iloc[i_te]
    fair = fairness(y[i_te], p_te, {"gender": test["gender"].reset_index(drop=True),
                                    "age_band": age_band(test["age"]).reset_index(drop=True)}, approve_pd)
    for k in ("gender", "age_band"):
        print(f"[fairness] {k}: DP diff={fair[k]['demographic_parity_difference']} "
              f"EO diff={fair[k]['equalized_odds_difference']}")

    bench = {} if args.no_benchmark else run_benchmark()

    # ------------------------------------------------------------------ save
    ART.mkdir(parents=True, exist_ok=True)
    model_path = ART / "model.txt"
    bst.save_model(str(model_path), num_iteration=bst.best_iteration)
    sha = hashlib.sha256(model_path.read_bytes()).hexdigest()[:8]
    version = f"lightgbm-pd-v1+{sha}"
    (ART / "calibrator.json").write_text(json.dumps({
        "method": "platt",
        "formula": "pd = 1 / (1 + exp(-(a * raw_log_odds + b)))",
        "a": round(a, 6), "b": round(b, 6),
        "fitted_on": f"synthetic calibration split (n={len(i_ca)})",
        "model_version": version,
        "features": FEATURES,
        "isotonic_reference": {  # stored for comparison only; production uses Platt
            "x_uncalibrated_pd": [round(float(v), 4) for v in iso.X_thresholds_][:200],
            "y_pd": [round(float(v), 5) for v in iso.y_thresholds_][:200],
        },
    }, indent=1), encoding="utf-8")

    metrics: dict[str, Any] = {
        "model_version": version,
        "trained_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "algorithm": "LightGBM gradient-boosted trees (monotone constraints) + Platt calibration",
        "params": {k: v for k, v in PARAMS.items() if k not in ("verbosity", "num_threads")},
        "best_iteration": int(bst.best_iteration),
        "monotone_constraints": dict(zip(FEATURES, monotone, strict=False)),
        "features": FEATURES,
        "feature_labels": FEATURE_LABELS,
        "data": {
            "kind": "SYNTHETIC",
            "generator": "backend/app/ml/synthetic.py (documented generative process)",
            "rows": len(df), "seed": SEED, "default_rate": round(float(y.mean()), 4),
            "splits": {"train": len(i_fit), "early_stopping": len(i_es), "calibration": len(i_ca),
                       "test": len(i_te)},
        },
        "test": {**m, "ece": ece(cal)},
        "test_uncalibrated": {"brier": round(float(brier_score_loss(y[i_te], p_uncal)), 5),
                              "ece": ece(calibration_table(y[i_te], p_uncal))},
        "test_isotonic": {"brier": round(float(brier_score_loss(y[i_te], p_iso)), 5),
                          "ece": ece(calibration_table(y[i_te], p_iso)),
                          "auc": round(float(roc_auc_score(y[i_te], p_iso)), 4)},
        "baselines": {"logistic_regression_auc": round(float(lr_auc), 4),
                      "fallback_scorecard": fb,
                      "oracle_true_pd_auc": round(float(oracle_auc), 4),
                      "note": "oracle = AUC of the generator's own true PD (ceiling given unobserved noise)"},
        "calibration": {"method": "platt", "a": round(a, 6), "b": round(b, 6), "deciles": cal},
        "pd_bands": band_rows,
        "shap_importance": imp,
        "fairness": fair,
        "benchmark": bench,
    }
    metrics["plots"] = plots(y[i_te], p_te, cal, imp, fair, m["auc"])
    (ART / "metrics.json").write_text(json.dumps(metrics, indent=1, default=str), encoding="utf-8")
    print(f"[save] {version} -> {ART}")


if __name__ == "__main__":
    main()
