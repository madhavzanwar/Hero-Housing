"""Sanity tests for the synthetic training-data generator."""
from __future__ import annotations

from app.ml.features import FEATURES
from app.ml.synthetic import generate


def test_generator_is_seeded_and_shaped() -> None:
    a = generate(n=3000, seed=1)
    b = generate(n=3000, seed=1)
    assert a.equals(b)
    assert set(FEATURES) <= set(a.columns)
    assert "gender" in a.columns and "gender" not in FEATURES
    assert a[FEATURES].notna().all().all()


def test_default_rate_and_risk_drivers() -> None:
    d = generate(n=20000, seed=3)
    assert 0.03 <= d["default"].mean() <= 0.05
    assert d.loc[d.bureau_score < 700, "default"].mean() > d.loc[d.bureau_score > 780, "default"].mean()
    assert d.loc[d.foir > 0.6, "default"].mean() > d.loc[d.foir < 0.35, "default"].mean()
