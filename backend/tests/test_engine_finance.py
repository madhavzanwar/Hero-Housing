from datetime import date

import pytest

from app.engine.finance import age_on, emi, fmt_inr, fmt_inr_short, principal_from_emi, round_down, tenure_for_emi


def test_emi_known_value_10l_85_240():
    assert emi(1_000_000, 0.085, 240) == pytest.approx(8678.23, abs=0.5)


def test_emi_known_value_45l_835_240():
    assert emi(4_500_000, 0.0835, 240) == pytest.approx(38625.9, abs=1)


def test_emi_zero_rate_and_edges():
    assert emi(120_000, 0.0, 12) == pytest.approx(10_000)
    assert emi(0, 0.09, 120) == 0
    assert emi(100_000, 0.09, 0) == 0


@pytest.mark.parametrize("p,r,n", [(1_000_000, 0.085, 240), (3_500_000, 0.0975, 180), (7_000_000, 0.09, 360), (500_000, 0.0, 60)])
def test_principal_from_emi_inverts_emi(p, r, n):
    assert principal_from_emi(emi(p, r, n), r, n) == pytest.approx(p, rel=1e-9)


def test_tenure_for_emi():
    assert tenure_for_emi(1_000_000, 0.085, emi(1_000_000, 0.085, 240)) == 240
    assert tenure_for_emi(1_000_000, 0.12, 9_000) is None  # EMI below monthly interest


def test_age_on():
    assert age_on(date(1990, 6, 15), date(2026, 6, 15)) == pytest.approx(36.0)
    assert age_on(date(1990, 6, 15), date(2026, 6, 14)) == pytest.approx(36.0, abs=0.01)
    assert age_on(date(1990, 6, 15), date(2025, 12, 15)) == pytest.approx(35.5, abs=0.01)
    assert age_on(None) == 0.0
    assert age_on(date(2000, 2, 29), date(2026, 3, 1)) == pytest.approx(26.0, abs=0.01)


@pytest.mark.parametrize("amount,expected", [
    (4_500_000, "₹45,00,000"), (12_345_678, "₹1,23,45,678"), (999, "₹999"), (1000, "₹1,000"),
    (100000, "₹1,00,000"), (0, "₹0"), (-250000, "-₹2,50,000"), (8678.23, "₹8,678"),
])
def test_fmt_inr(amount, expected):
    assert fmt_inr(amount) == expected


def test_fmt_inr_decimals_and_short():
    assert fmt_inr(8678.236, 2) == "₹8,678.24"
    assert fmt_inr_short(11_000_000) == "₹1.10 Cr"
    assert fmt_inr_short(4_500_000) == "₹45.0 L"


def test_round_down():
    assert round_down(2_789_999, 10_000) == 2_780_000
    assert round_down(0.9 * 3_100_000, 10_000) == 2_790_000
    assert round_down(-5, 10_000) == 0
