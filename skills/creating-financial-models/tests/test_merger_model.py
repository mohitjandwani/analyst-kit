"""
Tests for the M&A merger / accretion-dilution model.

The cross-check test reproduces a known-good, hand-verified deal scenario to
confirm the accretion/dilution formulas are correct: a 60/40 stock/cash deal at
a 20% premium should be +7.52% accretive with pro forma EPS of $4.30. The rest
stress the additions (PPA amortization, breakeven synergies) and the guard
rails.

Run from the skill root:  python3 -m pytest tests/ -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from merger_model import MergerModel
from sensitivity_analysis import SensitivityAnalyzer


def reference_deal(**deal_overrides):
    """The cross-check scenario; deal terms overridable per test."""
    model = MergerModel("ABC / XYZ")
    model.set_acquirer("ABC", share_price=50.0, shares_outstanding=200_000_000,
                       net_income=800_000_000)
    model.set_target("XYZ", share_price=25.0, shares_outstanding=100_000_000,
                     net_income=200_000_000)
    terms = dict(
        offer_price_per_share=30.0,
        stock_percentage=0.6,
        cash_percentage=0.4,
        tax_rate=0.25,
        synergies_pre_tax=50_000_000,
        debt_portion_of_cash=0.5,
        cost_of_new_debt=0.03,
        foregone_cash_yield=0.02,
    )
    terms.update(deal_overrides)
    model.set_deal_terms(**terms)
    return model


# ----------------------------------------------- independent cross-check


def test_matches_known_good_scenario():
    """Reproduce the known-good scenario's headline numbers exactly."""
    r = reference_deal().analyze()
    st, pf = r["structure"], r["pro_forma"]

    assert st["equity_purchase_price"] == pytest.approx(3_000_000_000)
    assert st["premium_to_market"] == pytest.approx(0.20)
    assert st["new_shares_issued"] == pytest.approx(36_000_000)
    assert st["proforma_shares"] == pytest.approx(236_000_000)
    assert pf["proforma_net_income"] == pytest.approx(1_015_000_000)
    assert pf["acquirer_eps"] == pytest.approx(4.00)
    assert pf["proforma_eps"] == pytest.approx(4.3008, abs=1e-4)
    assert pf["accretion_dilution"] == pytest.approx(0.0752, abs=1e-4)
    assert pf["is_accretive"] is True


def test_pre_deal_metrics():
    pre = reference_deal().pre_deal_metrics()
    assert pre["acquirer"]["eps"] == pytest.approx(4.00)
    assert pre["acquirer"]["pe"] == pytest.approx(12.5)
    assert pre["target"]["eps"] == pytest.approx(2.00)
    assert pre["target"]["pe"] == pytest.approx(12.5)


# ----------------------------------------------- PPA amortization (the addition)


def test_ppa_amortization_flips_deal_to_dilutive():
    """The headline reason to build our own: a deal accretive on a paper basis
    goes dilutive once purchase-price-allocation amortization is recognized."""
    base = reference_deal().analyze()["pro_forma"]
    assert base["is_accretive"]

    with_ppa = reference_deal(
        new_intangibles=1_500_000_000,
        intangible_amortization_years=10,
        amortization_tax_deductible=False,
    ).analyze()["pro_forma"]

    assert with_ppa["amortization_after_tax"] == pytest.approx(150_000_000)
    assert with_ppa["proforma_eps"] < base["proforma_eps"]
    assert not with_ppa["is_accretive"]


def test_amortization_tax_shield_matters():
    """A deductible amortization (asset deal) hurts EPS less than a
    non-deductible one (stock deal), by exactly the tax shield."""
    deductible = reference_deal(
        new_intangibles=1_000_000_000, intangible_amortization_years=10,
        amortization_tax_deductible=True,
    ).analyze()["pro_forma"]
    non_deductible = reference_deal(
        new_intangibles=1_000_000_000, intangible_amortization_years=10,
        amortization_tax_deductible=False,
    ).analyze()["pro_forma"]

    # annual amort = 100M; deductible after-tax = 75M, non-deductible = 100M
    assert deductible["amortization_after_tax"] == pytest.approx(75_000_000)
    assert non_deductible["amortization_after_tax"] == pytest.approx(100_000_000)
    assert deductible["proforma_eps"] > non_deductible["proforma_eps"]


# ----------------------------------------------- breakeven synergies


def test_breakeven_synergies_round_trip():
    """Plugging the breakeven synergy level back in yields a ~0% EPS change."""
    be = reference_deal().breakeven_synergies()
    at_breakeven = reference_deal(synergies_pre_tax=be).analyze()["pro_forma"]
    assert at_breakeven["accretion_dilution"] == pytest.approx(0.0, abs=1e-9)


def test_breakeven_negative_when_accretive_without_synergies():
    """The base deal is accretive even at zero synergies, so the breakeven
    (the dis-synergy it can absorb) is negative."""
    no_syn = reference_deal(synergies_pre_tax=0.0).analyze()["pro_forma"]
    assert no_syn["is_accretive"]
    assert reference_deal().breakeven_synergies() < 0


# ----------------------------------------------- consideration mix


def test_all_stock_deal_has_no_financing_drag():
    pf = reference_deal(stock_percentage=1.0, cash_percentage=0.0).analyze()["pro_forma"]
    assert pf["financing_after_tax"] == pytest.approx(0.0)
    assert pf["interest_expense"] == pytest.approx(0.0)
    assert pf["foregone_interest"] == pytest.approx(0.0)


def test_all_cash_deal_issues_no_shares():
    r = reference_deal(stock_percentage=0.0, cash_percentage=1.0).analyze()
    assert r["structure"]["new_shares_issued"] == pytest.approx(0.0)
    assert r["structure"]["proforma_shares"] == pytest.approx(200_000_000)


def test_private_target_premium_and_pe_are_none():
    """A private target (no share price) still produces an EPS impact, but
    premium and standalone P/E are undefined rather than crashing."""
    model = MergerModel("Acq / Private")
    model.set_acquirer("Acq", 50.0, 200_000_000, 800_000_000)
    model.set_target("Private", share_price=0.0, shares_outstanding=100_000_000,
                     net_income=200_000_000)
    model.set_deal_terms(offer_price_per_share=30.0, stock_percentage=0.6,
                         cash_percentage=0.4)
    r = model.analyze()
    assert r["structure"]["premium_to_market"] is None
    assert r["pre_deal"]["target"]["pe"] is None
    assert r["pro_forma"]["proforma_eps"] > 0


# ----------------------------------------------- guard rails (raise, not None)


def test_consideration_must_sum_to_one():
    with pytest.raises(ValueError, match="must equal 100%"):
        reference_deal(stock_percentage=0.6, cash_percentage=0.5).deal_structure()


def test_zero_acquirer_price_raises():
    model = MergerModel()
    model.set_acquirer("A", share_price=0.0, shares_outstanding=100, net_income=100)
    model.set_target("T", 10.0, 50, 50)
    model.set_deal_terms(offer_price_per_share=12.0, stock_percentage=0.5,
                         cash_percentage=0.5)
    with pytest.raises(ValueError, match="share price must be > 0"):
        model.deal_structure()


def test_intangibles_without_life_raises():
    with pytest.raises(ValueError, match="intangible_amortization_years"):
        reference_deal(new_intangibles=1_000_000, intangible_amortization_years=0).analyze()


def test_unset_inputs_raise():
    with pytest.raises(ValueError, match="Acquirer financials not set"):
        MergerModel().pre_deal_metrics()


# ----------------------------------------------- composes with SensitivityAnalyzer


def test_synergy_sensitivity_via_analyzer():
    """The merger model plugs into the existing sensitivity engine: sweep
    synergies, read accretion/dilution as the output."""
    model = reference_deal()
    analyzer = SensitivityAnalyzer(model)

    def set_synergies(value):
        model.deal["synergies_pre_tax"] = value

    def accretion():
        return model.pro_forma_eps()["accretion_dilution"]

    df = analyzer.one_way_sensitivity(
        "synergies_pre_tax", base_value=50_000_000, range_pct=0.5, steps=5,
        output_func=accretion, model_update_func=set_synergies,
    )
    assert len(df) == 5
    # accretion rises monotonically with synergies
    assert df["output"].is_monotonic_increasing
    # model restored to base synergies afterwards
    assert model.deal["synergies_pre_tax"] == pytest.approx(50_000_000)
