"""
M&A merger model — accretion/dilution analysis.

Given an acquirer, a target, and deal terms (offer price, stock/cash mix,
financing, synergies, purchase-price allocation), computes the pro forma EPS of
the combined company and whether the deal is accretive or dilutive to the
acquirer's standalone EPS — the first question an acquirer's board asks.

Pure calculation: methods return dicts and raise on invalid input. No I/O, no
module-level state, importable. Requires no third-party packages.

The accretion/dilution mechanics (consideration split, new shares issued,
after-tax synergies, financing drag from new debt and foregone interest on
balance-sheet cash) follow the standard "paper merger model" taught in
investment banking. The PPA intangible amortization, transaction/financing
fees, breakeven-synergies solve, and premium calculation are first-class here
because they routinely flip a deal that looks accretive on a back-of-envelope
basis into dilutive on a GAAP basis.
"""

from __future__ import annotations

from typing import Any


class MergerModel:
    """Build and evaluate an M&A accretion/dilution model."""

    def __init__(self, deal_name: str = "M&A Deal"):
        self.deal_name = deal_name
        self.acquirer: dict[str, float] = {}
        self.target: dict[str, float] = {}
        self.deal: dict[str, Any] = {}

    # ------------------------------------------------------------------ inputs

    def set_acquirer(
        self, name: str, share_price: float, shares_outstanding: float, net_income: float
    ) -> None:
        """Acquirer standalone financials (shares in absolute units, not millions)."""
        self.acquirer = {
            "name": name,
            "share_price": share_price,
            "shares_outstanding": shares_outstanding,
            "net_income": net_income,
        }

    def set_target(
        self, name: str, share_price: float, shares_outstanding: float, net_income: float
    ) -> None:
        """Target standalone financials. ``share_price`` may be 0 for a private target
        (only used to report the premium and the target's standalone P/E)."""
        self.target = {
            "name": name,
            "share_price": share_price,
            "shares_outstanding": shares_outstanding,
            "net_income": net_income,
        }

    def set_deal_terms(
        self,
        offer_price_per_share: float,
        stock_percentage: float,
        cash_percentage: float,
        tax_rate: float = 0.25,
        synergies_pre_tax: float = 0.0,
        debt_portion_of_cash: float = 1.0,
        cost_of_new_debt: float = 0.0,
        foregone_cash_yield: float = 0.0,
        new_intangibles: float = 0.0,
        intangible_amortization_years: float = 0.0,
        amortization_tax_deductible: bool = True,
        financing_fee_amortization: float = 0.0,
    ) -> None:
        """
        Deal terms and financing assumptions.

        Args:
            offer_price_per_share: Price offered per target share.
            stock_percentage: Fraction of consideration paid in acquirer stock.
            cash_percentage: Fraction paid in cash (stock + cash must sum to 1).
            tax_rate: Marginal tax rate applied to synergies, financing, and
                (when deductible) intangible amortization.
            synergies_pre_tax: Annual run-rate pre-tax synergies.
            debt_portion_of_cash: Fraction of the *cash* consideration funded by
                new debt; the remainder is funded from balance-sheet cash.
            cost_of_new_debt: Pre-tax interest rate on the new debt.
            foregone_cash_yield: Pre-tax yield given up on balance-sheet cash used.
            new_intangibles: Identifiable intangible assets created by purchase-
                price allocation (amortizable). Goodwill is not amortized, so do
                not include it here.
            intangible_amortization_years: Useful life over which the intangibles
                amortize (required when ``new_intangibles`` > 0).
            amortization_tax_deductible: If True, amortization carries a tax
                shield (after-tax hit = amort x (1 - tax)); typical for taxable
                asset deals / 338(h)(10). If False (typical stock deals), the
                full book amortization hits net income with no shield.
            financing_fee_amortization: Annual recurring pre-tax amortization of
                capitalized financing fees, if any.
        """
        self.deal = {
            "offer_price_per_share": offer_price_per_share,
            "stock_percentage": stock_percentage,
            "cash_percentage": cash_percentage,
            "tax_rate": tax_rate,
            "synergies_pre_tax": synergies_pre_tax,
            "debt_portion_of_cash": debt_portion_of_cash,
            "cost_of_new_debt": cost_of_new_debt,
            "foregone_cash_yield": foregone_cash_yield,
            "new_intangibles": new_intangibles,
            "intangible_amortization_years": intangible_amortization_years,
            "amortization_tax_deductible": amortization_tax_deductible,
            "financing_fee_amortization": financing_fee_amortization,
        }

    # ------------------------------------------------------------- validation

    def _require_inputs(self) -> None:
        if not self.acquirer:
            raise ValueError("Acquirer financials not set — call set_acquirer() first.")
        if not self.target:
            raise ValueError("Target financials not set — call set_target() first.")
        if not self.deal:
            raise ValueError("Deal terms not set — call set_deal_terms() first.")

        stock = self.deal["stock_percentage"]
        cash = self.deal["cash_percentage"]
        if abs((stock + cash) - 1.0) > 1e-6:
            raise ValueError(
                f"Stock % ({stock:.1%}) + cash % ({cash:.1%}) must equal 100%."
            )
        for pct, label in [
            (stock, "stock_percentage"),
            (cash, "cash_percentage"),
            (self.deal["debt_portion_of_cash"], "debt_portion_of_cash"),
            (self.deal["tax_rate"], "tax_rate"),
        ]:
            if not 0.0 <= pct <= 1.0:
                raise ValueError(f"{label} must be between 0 and 1, got {pct}.")
        if self.deal["new_intangibles"] > 0 and self.deal["intangible_amortization_years"] <= 0:
            raise ValueError(
                "intangible_amortization_years must be > 0 when new_intangibles > 0."
            )

    # ---------------------------------------------------------- computations

    @staticmethod
    def _company_metrics(company: dict[str, float]) -> dict[str, float | None]:
        price = company["share_price"]
        shares = company["shares_outstanding"]
        ni = company["net_income"]
        eps = ni / shares if shares > 0 else None
        pe = price / eps if (price > 0 and eps not in (None, 0)) else None
        return {"market_cap": price * shares, "eps": eps, "pe": pe}

    def pre_deal_metrics(self) -> dict[str, Any]:
        """Standalone market cap, EPS, and P/E for acquirer and target."""
        self._require_inputs()
        return {
            "acquirer": self._company_metrics(self.acquirer),
            "target": self._company_metrics(self.target),
        }

    def deal_structure(self) -> dict[str, float]:
        """Consideration split, new shares issued, pro forma share count, premium."""
        self._require_inputs()

        if self.acquirer["share_price"] <= 0:
            raise ValueError("Acquirer share price must be > 0 to value stock issued.")

        offer = self.deal["offer_price_per_share"]
        target_shares = self.target["shares_outstanding"]
        equity_value = offer * target_shares

        stock_consideration = self.deal["stock_percentage"] * equity_value
        cash_consideration = self.deal["cash_percentage"] * equity_value
        new_shares = stock_consideration / self.acquirer["share_price"]
        proforma_shares = self.acquirer["shares_outstanding"] + new_shares

        target_price = self.target["share_price"]
        premium = (offer / target_price - 1.0) if target_price > 0 else None

        return {
            "equity_purchase_price": equity_value,
            "premium_to_market": premium,
            "stock_consideration": stock_consideration,
            "cash_consideration": cash_consideration,
            "new_shares_issued": new_shares,
            "proforma_shares": proforma_shares,
        }

    def _financing_and_amortization(self, structure: dict[str, float]) -> dict[str, float]:
        """After-tax recurring drags: financing (new debt + foregone cash) and PPA."""
        d = self.deal
        tax = d["tax_rate"]
        cash_consideration = structure["cash_consideration"]

        debt_funded = cash_consideration * d["debt_portion_of_cash"]
        cash_funded = cash_consideration * (1 - d["debt_portion_of_cash"])

        interest_expense = debt_funded * d["cost_of_new_debt"]
        foregone_interest = cash_funded * d["foregone_cash_yield"]
        fee_amort = d["financing_fee_amortization"]
        financing_after_tax = (interest_expense + foregone_interest + fee_amort) * (1 - tax)

        years = d["intangible_amortization_years"]
        annual_amort = d["new_intangibles"] / years if years > 0 else 0.0
        if d["amortization_tax_deductible"]:
            amort_after_tax = annual_amort * (1 - tax)
        else:
            amort_after_tax = annual_amort  # no tax shield (typical stock deal)

        return {
            "debt_funded_cash": debt_funded,
            "cash_funded_cash": cash_funded,
            "interest_expense": interest_expense,
            "foregone_interest": foregone_interest,
            "financing_fee_amortization": fee_amort,
            "financing_after_tax": financing_after_tax,
            "annual_intangible_amortization": annual_amort,
            "amortization_after_tax": amort_after_tax,
        }

    def pro_forma_eps(self) -> dict[str, Any]:
        """
        Pro forma net income and EPS, and the accretion/dilution to the
        acquirer's standalone EPS.

        Pro forma NI = acquirer NI + target NI + after-tax synergies
                       - after-tax financing drag - after-tax PPA amortization
        """
        self._require_inputs()
        structure = self.deal_structure()

        acq_shares = self.acquirer["shares_outstanding"]
        if acq_shares <= 0:
            raise ValueError("Acquirer shares outstanding must be > 0 to compute EPS.")
        proforma_shares = structure["proforma_shares"]
        if proforma_shares <= 0:
            raise ValueError("Pro forma shares must be > 0 to compute EPS.")

        tax = self.deal["tax_rate"]
        acquirer_eps = self.acquirer["net_income"] / acq_shares
        after_tax_synergies = self.deal["synergies_pre_tax"] * (1 - tax)
        drag = self._financing_and_amortization(structure)

        proforma_ni = (
            self.acquirer["net_income"]
            + self.target["net_income"]
            + after_tax_synergies
            - drag["financing_after_tax"]
            - drag["amortization_after_tax"]
        )
        proforma_eps = proforma_ni / proforma_shares
        accretion_dilution = (proforma_eps - acquirer_eps) / acquirer_eps

        return {
            "acquirer_eps": acquirer_eps,
            "proforma_eps": proforma_eps,
            "proforma_net_income": proforma_ni,
            "accretion_dilution": accretion_dilution,
            "is_accretive": accretion_dilution >= 0,
            "after_tax_synergies": after_tax_synergies,
            **drag,
        }

    def breakeven_synergies(self) -> float:
        """
        Pre-tax annual synergies at which the deal is exactly EPS-neutral.

        Solve proforma_eps == acquirer_eps for synergies. A negative result
        means the deal is accretive even with zero synergies (it can absorb
        that much pre-tax dis-synergy and stay neutral).
        """
        self._require_inputs()
        structure = self.deal_structure()
        tax = self.deal["tax_rate"]
        if tax >= 1.0:
            raise ValueError("tax_rate must be < 1 to solve for breakeven synergies.")

        acq_shares = self.acquirer["shares_outstanding"]
        acquirer_eps = self.acquirer["net_income"] / acq_shares
        proforma_shares = structure["proforma_shares"]
        drag = self._financing_and_amortization(structure)

        required_after_tax = (
            acquirer_eps * proforma_shares
            - self.acquirer["net_income"]
            - self.target["net_income"]
            + drag["financing_after_tax"]
            + drag["amortization_after_tax"]
        )
        return required_after_tax / (1 - tax)

    def analyze(self) -> dict[str, Any]:
        """Run the full analysis and return all results in one dict."""
        return {
            "deal_name": self.deal_name,
            "pre_deal": self.pre_deal_metrics(),
            "structure": self.deal_structure(),
            "pro_forma": self.pro_forma_eps(),
            "breakeven_synergies_pre_tax": self.breakeven_synergies(),
        }

    def generate_summary(self) -> str:
        """Human-readable summary of the deal and its EPS impact."""
        r = self.analyze()
        pf = r["pro_forma"]
        st = r["structure"]
        verdict = "ACCRETIVE" if pf["is_accretive"] else "DILUTIVE"
        premium = st["premium_to_market"]
        premium_str = f"{premium:.1%}" if premium is not None else "n/a (private target)"

        return "\n".join(
            [
                f"Merger Analysis — {self.deal_name}",
                "=" * 50,
                f"  {self.acquirer['name']} acquires {self.target['name']}",
                "",
                "Deal Structure:",
                f"  Equity purchase price: ${st['equity_purchase_price']:,.0f}",
                f"  Premium to market:     {premium_str}",
                f"  Stock / cash split:    "
                f"{self.deal['stock_percentage']:.0%} / {self.deal['cash_percentage']:.0%}",
                f"  New shares issued:     {st['new_shares_issued']:,.0f}",
                f"  Pro forma shares:      {st['proforma_shares']:,.0f}",
                "",
                "EPS Impact:",
                f"  Acquirer standalone EPS: ${pf['acquirer_eps']:.2f}",
                f"  Pro forma EPS:           ${pf['proforma_eps']:.2f}",
                f"  Accretion / (dilution):  {pf['accretion_dilution']:+.2%}",
                f"  After-tax synergies:     ${pf['after_tax_synergies']:,.0f}",
                f"  After-tax financing drag: ${pf['financing_after_tax']:,.0f}",
                f"  After-tax PPA amort:     ${pf['amortization_after_tax']:,.0f}",
                f"  Breakeven synergies (pre-tax): "
                f"${r['breakeven_synergies_pre_tax']:,.0f}",
                "",
                f"Result: {verdict}",
            ]
        )


# Example usage
if __name__ == "__main__":
    # Same inputs as a canonical paper merger model: a 20% premium, 60/40
    # stock/cash, modest synergies. With no PPA amortization this is a clean
    # accretion/dilution check.
    model = MergerModel("ABC Corp / XYZ Ltd")
    model.set_acquirer("ABC Corp", share_price=50.0, shares_outstanding=200_000_000,
                       net_income=800_000_000)
    model.set_target("XYZ Ltd", share_price=25.0, shares_outstanding=100_000_000,
                     net_income=200_000_000)
    model.set_deal_terms(
        offer_price_per_share=30.0,
        stock_percentage=0.6,
        cash_percentage=0.4,
        tax_rate=0.25,
        synergies_pre_tax=50_000_000,
        debt_portion_of_cash=0.5,
        cost_of_new_debt=0.03,
        foregone_cash_yield=0.02,
    )
    print(model.generate_summary())

    print("\n--- Same deal, now with $1.5bn of PPA intangibles over 10y (stock deal) ---")
    model.set_deal_terms(
        offer_price_per_share=30.0,
        stock_percentage=0.6,
        cash_percentage=0.4,
        tax_rate=0.25,
        synergies_pre_tax=50_000_000,
        debt_portion_of_cash=0.5,
        cost_of_new_debt=0.03,
        foregone_cash_yield=0.02,
        new_intangibles=1_500_000_000,
        intangible_amortization_years=10,
        amortization_tax_deductible=False,
    )
    print(model.generate_summary())
