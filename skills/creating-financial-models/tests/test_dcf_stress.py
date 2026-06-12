"""
Stress-test scenarios for the DCF model and sensitivity tools.

Each test is a realistic analyst scenario pushed to an edge: aggressive
terminal assumptions, cash-burning companies, declining revenue, grid
sensitivity across invalid regions, and bad inputs. Tests that pin down a
known sharp edge (rather than desired behavior) say so in their docstring.

Run from the skill root:  python3 -m pytest tests/ -v
"""

import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from dcf_model import DCFModel, calculate_beta, calculate_fcf_cagr
from sensitivity_analysis import SensitivityAnalyzer


def build_model(
    revenue_growth=None,
    ebitda_margin=None,
    terminal_growth=0.03,
    capex_percent=None,
    nwc_percent=None,
    wacc_inputs=None,
    years=5,
):
    """A 'TechCorp'-style model with overridable assumptions."""
    model = DCFModel("StressCorp")
    model.set_historical_financials(
        revenue=[800, 900, 1000],
        ebitda=[160, 189, 220],
        capex=[40, 45, 50],
        nwc=[80, 90, 100],
        years=[2022, 2023, 2024],
    )
    model.set_assumptions(
        projection_years=years,
        revenue_growth=revenue_growth or [0.10] * years,
        ebitda_margin=ebitda_margin or [0.22] * years,
        tax_rate=0.25,
        capex_percent=capex_percent,
        nwc_percent=nwc_percent,
        terminal_growth=terminal_growth,
    )
    wacc_inputs = wacc_inputs or dict(
        risk_free_rate=0.04, beta=1.2, market_premium=0.07, cost_of_debt=0.05, debt_to_equity=0.5
    )
    model.calculate_wacc(**wacc_inputs)
    return model


# ---------------------------------------------------------------- base case


def test_base_case_is_sane():
    model = build_model()
    results = model.calculate_enterprise_value()
    assert results["enterprise_value"] > 0
    assert 0 < results["terminal_percent"] < 100
    equity = model.calculate_equity_value(net_debt=200, shares_outstanding=50)
    assert equity["value_per_share"] > 0


def test_exit_multiple_matches_hand_calculation():
    model = build_model()
    model.project_cash_flows()
    tv = model.calculate_terminal_value("multiple", exit_multiple=12)
    assert tv == pytest.approx(model.projections["ebitda"][-1] * 12)


# ------------------------------------------------- terminal value guard


def test_terminal_growth_above_wacc_raises():
    """Aggressive terminal growth must fail loudly, not return negative TV."""
    model = build_model(terminal_growth=0.12)  # WACC ~9.2%
    model.project_cash_flows()
    with pytest.raises(ValueError, match="must exceed terminal growth"):
        model.calculate_terminal_value("growth")


def test_terminal_growth_equal_to_wacc_raises():
    model = build_model()
    model.wacc_components["wacc"] = model.assumptions["terminal_growth"]
    model.project_cash_flows()
    with pytest.raises(ValueError):
        model.calculate_terminal_value("growth")


def test_exit_multiple_unaffected_by_terminal_growth_guard():
    """The multiple method has no growth/WACC constraint and must still work."""
    model = build_model(terminal_growth=0.12)
    results = model.calculate_enterprise_value(terminal_method="multiple", exit_multiple=10)
    assert results["enterprise_value"] > 0


# ------------------------------------------------- stressed operating cases


def test_cash_burning_company_yields_negative_ev():
    """Thin margins + heavy capex/NWC: FCF is negative every year. A negative
    EV is the mathematically consistent answer; it must not crash."""
    model = build_model(
        ebitda_margin=[0.05] * 5,
        capex_percent=[0.04] * 5,
        nwc_percent=[0.30] * 5,
    )
    results = model.calculate_enterprise_value()
    assert all(f < 0 for f in model.projections["fcf"])
    assert results["enterprise_value"] < 0


def test_declining_revenue_company():
    """Melting-ice-cube scenario: -8% revenue per year still values cleanly."""
    model = build_model(revenue_growth=[-0.08] * 5, terminal_growth=0.0)
    results = model.calculate_enterprise_value()
    assert model.projections["revenue"][-1] < 1000
    assert results["enterprise_value"] > 0  # shrinking but FCF-positive


def test_negative_ebit_gets_tax_benefit():
    """When D&A (== capex) exceeds EBITDA, EBIT < 0 and the model books a
    negative tax (a full immediate tax shield). That is an upstream modeling
    assumption — no NOL carryforward logic — pinned here so a change is
    deliberate."""
    model = build_model(ebitda_margin=[0.03] * 5, capex_percent=[0.06] * 5)
    model.project_cash_flows()
    assert all(e < 0 for e in model.projections["ebit"])
    assert all(t < 0 for t in model.projections["tax"])


def test_zero_shares_outstanding_does_not_divide_by_zero():
    model = build_model()
    model.calculate_enterprise_value()
    equity = model.calculate_equity_value(net_debt=0, shares_outstanding=0)
    assert equity["value_per_share"] == 0


# ------------------------------------------------- two-way sensitivity grid


def test_sensitivity_grid_survives_invalid_growth_cells():
    """Grid spans terminal growth 1%..11% against a ~9.2% WACC. Cells where
    growth >= WACC are invalid for Gordon growth; they must come back NaN
    while the valid cells still compute."""
    model = build_model()
    grid = model.sensitivity_analysis(
        "growth", [0.01, 0.03, 0.11], "margin", [0.20, 0.25]
    )
    assert grid.shape == (3, 2)
    assert not np.isnan(grid[0]).any()  # growth 1% — valid
    assert not np.isnan(grid[1]).any()  # growth 3% — valid
    assert np.isnan(grid[2]).all()  # growth 11% > WACC — invalid, not negative
    # model state restored
    assert model.assumptions["terminal_growth"] == 0.03


def test_sensitivity_grid_wacc_axis():
    model = build_model()
    grid = model.sensitivity_analysis(
        "wacc", [0.02, 0.08, 0.12], "growth", [0.03]
    )
    assert np.isnan(grid[0, 0])  # WACC 2% < growth 3% — invalid
    assert grid[1, 0] > grid[2, 0] > 0  # lower WACC → higher value


# ------------------------------------------------- known sharp edges (inputs)


def test_zero_revenue_year_raises_zero_division():
    """KNOWN SHARP EDGE: a zero-revenue historical year breaks margin math in
    set_historical_financials. Callers must filter zero-revenue periods."""
    model = DCFModel("ZeroRev")
    with pytest.raises(ZeroDivisionError):
        model.set_historical_financials(
            revenue=[0, 900, 1000],
            ebitda=[0, 189, 220],
            capex=[0, 45, 50],
            nwc=[0, 90, 100],
            years=[2022, 2023, 2024],
        )


def test_short_growth_list_raises_index_error():
    """KNOWN SHARP EDGE: fewer growth rates than projection years fails with
    IndexError at projection time, not at assumption time."""
    model = build_model()
    model.assumptions["revenue_growth"] = [0.10, 0.10]  # 2 rates, 5 years
    with pytest.raises(IndexError):
        model.project_cash_flows()


# ------------------------------------------------- helpers


def test_beta_with_flat_market_defaults_to_one():
    assert calculate_beta([0.01, 0.02, 0.03], [0.01, 0.01, 0.01]) == 1.0


def test_fcf_cagr_with_negative_fcf_returns_zero():
    assert calculate_fcf_cagr([-100, 50, 120]) == 0


# ------------------------------------------------- analyzer over a real DCF


def test_breakeven_wacc_against_real_dcf():
    """Inverse-relationship breakeven on the actual model: find the WACC at
    which EV equals a target, then confirm by recomputation."""
    model = build_model()
    target_ev = 2500.0

    def set_wacc(w):
        model.wacc_components["wacc"] = w

    def ev():
        model.project_cash_flows()
        return model.calculate_enterprise_value()["enterprise_value"]

    analyzer = SensitivityAnalyzer(model)
    be_wacc = analyzer.breakeven_analysis(
        "wacc", set_wacc, ev, target_value=target_ev,
        min_search=0.05, max_search=0.30, tolerance=1e-5,
    )
    set_wacc(be_wacc)
    assert ev() == pytest.approx(target_ev, rel=0.01)


def test_scenario_analysis_on_real_dcf_restores_base():
    model = build_model()

    def set_growth(g):
        model.assumptions["revenue_growth"] = [g] * 5

    def set_margin(m):
        model.assumptions["ebitda_margin"] = [m] * 5

    def ev():
        model.project_cash_flows()
        return model.calculate_enterprise_value()["enterprise_value"]

    analyzer = SensitivityAnalyzer(model)
    df = analyzer.scenario_analysis(
        scenarios={
            "bear": {"growth": 0.02, "margin": 0.18},
            "base": {"growth": 0.10, "margin": 0.22},
            "bull": {"growth": 0.15, "margin": 0.26},
        },
        variable_updates={"growth": set_growth, "margin": set_margin},
        output_func=ev,
        probability_weights={"bear": 0.25, "base": 0.5, "bull": 0.25},
        base_values={"growth": 0.10, "margin": 0.22},
    )
    outputs = df.set_index("scenario")["output"]
    assert outputs["bear"] < outputs["base"] < outputs["bull"]
    expected = df[df.scenario == "Expected Value"]["output"].iloc[0]
    assert outputs["bear"] < expected < outputs["bull"]
    assert model.assumptions["ebitda_margin"] == [0.22] * 5  # restored
