import pytest

from app.policy.loader import get_policy, load_policy
from app.schemas import Product, RuleCategory

P = get_policy()


def test_load_and_cache():
    assert P.version == "2026.11-v1"
    assert get_policy() is P
    assert load_policy().version == P.version
    assert isinstance(P.raw, dict)


@pytest.mark.parametrize("income,rid,cap", [
    (30000, "ELG-FOIR-01", 0.50), (50000, "ELG-FOIR-01", 0.50), (50001, "ELG-FOIR-02", 0.55),
    (100000, "ELG-FOIR-02", 0.55), (150000, "ELG-FOIR-03", 0.60), (200001, "ELG-FOIR-04", 0.65),
])
def test_foir_bands(income, rid, cap):
    assert P.foir_cap(income) == (rid, cap)


@pytest.mark.parametrize("loan,rid,cap", [
    (2_500_000, "LTV-HL-01", 0.90), (3_000_000, "LTV-HL-01", 0.90), (3_000_001, "LTV-HL-02", 0.80),
    (7_500_000, "LTV-HL-02", 0.80), (7_500_001, "LTV-HL-03", 0.75), (20_000_000, "LTV-HL-03", 0.75),
])
def test_ltv_slabs(loan, rid, cap):
    got = P.ltv_cap(Product.HOME_LOAN, loan, "RESIDENTIAL")
    assert got[:2] == (rid, cap)
    assert "RBI" in got[2]


@pytest.mark.parametrize("ptype,rid,cap", [("RESIDENTIAL", "LTV-LAP-01", 0.65), ("COMMERCIAL", "LTV-LAP-02", 0.55),
                                          ("PLOT", "LTV-LAP-03", 0.50)])
def test_lap_caps(ptype, rid, cap):
    got = P.ltv_cap("LAP", 1_000_000, ptype)
    assert got[:2] == (rid, cap)


def test_max_loan_by_ltv_slab_interaction():
    # 40L property: 30L slab gives min(30L, 36L)=30L, 80% slab gives 32L -> 32L
    assert P.max_loan_by_ltv(Product.HOME_LOAN, 4_000_000)[0] == pytest.approx(3_200_000)
    # 33L property: 90% -> 29.7L beats 80% -> 26.4L
    amt, rid, cap = P.max_loan_by_ltv(Product.HOME_LOAN, 3_300_000)
    assert amt == pytest.approx(2_970_000) and rid == "LTV-HL-01" and cap == 0.9
    assert P.max_loan_by_ltv(Product.HOME_LOAN, 31_000_00)[0] == pytest.approx(2_790_000)
    assert P.max_loan_by_ltv(Product.HOME_LOAN, 16_000_000)[0] == pytest.approx(12_000_000)
    assert P.max_loan_by_ltv(Product.LAP, 15_000_000, "COMMERCIAL")[0] == pytest.approx(8_250_000)


def test_refs_and_rule_catalogue():
    assert P.ref("RBI_KFS").startswith("RBI circular")
    assert P.ref("free text") == "free text"
    assert P.ref(None) == ""
    for rid, meta in P.section("rules").items():
        RuleCategory(meta["category"])
        assert meta["name"]
        if meta.get("ref"):
            assert meta["ref"] in P.section("references"), rid
    for band in P.get("eligibility.foir_bands"):
        assert band["id"] in P.section("rules")
    assert "LAP" in P.rule_reference("LTV-LAP-01")


def test_get_dotted():
    assert P.get("banking.max_bounces_6m") == 2
    assert P.get("nope.nothing", 5) == 5


def test_negative_list():
    entries = P.negative_list()
    assert len(entries) >= 15
    assert {e["type"] for e in entries} == {"PEP", "SANCTIONS", "INTERNAL_DEFAULTER", "FRAUD_DB"}
    p11 = [e for e in entries if e["name"] == "Vikram Rathore Singhania"]
    assert p11 and p11[0]["type"] == "PEP"
    for e in entries:
        if e.get("pan_masked"):
            assert e["pan_masked"].startswith("XXXXX")
