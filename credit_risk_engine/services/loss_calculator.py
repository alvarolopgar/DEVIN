"""
Loss calculation service.

Implements Loss Given Default (LGD) and Exposure at Default (EAD)
calculations, producing Expected Loss (EL = PD × LGD × EAD) estimates
aligned with Basel II/III regulatory framework.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from credit_risk_engine.config.settings import LGDParameters
from credit_risk_engine.domain.enums import CreditProductType, PaymentStatus
from credit_risk_engine.domain.models import CreditPosition

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LossEstimate:
    """Loss estimate for a single credit position."""

    position_id: str
    product_type: CreditProductType
    lgd: float
    ead: float
    expected_loss: float  # PD × LGD × EAD (requires PD from caller)


@dataclass(frozen=True)
class ClientLossEstimate:
    """Aggregated loss estimate for a client across all positions."""

    client_id: str
    total_ead: float
    weighted_lgd: float  # EAD-weighted average LGD
    total_expected_loss: float
    position_losses: list[LossEstimate]


class LossCalculator:
    """
    Calculates Loss Given Default (LGD) and Exposure at Default (EAD).

    LGD estimation considers:
    - Product type (secured vs. unsecured)
    - Collateral coverage (LTV for secured products)
    - Seniority and recovery assumptions
    - Restructuring adjustments

    EAD estimation considers:
    - Outstanding balance
    - Undrawn credit commitments (Credit Conversion Factor)
    - Product type characteristics

    Args:
        lgd_params: LGD parameters by product type.
    """

    # Credit Conversion Factors (CCF) for undrawn commitments
    _CCF: dict[CreditProductType, float] = {
        CreditProductType.MORTGAGE: 1.0,        # Fully drawn
        CreditProductType.PERSONAL_LOAN: 1.0,   # Fully drawn
        CreditProductType.CREDIT_CARD: 0.75,    # Partially undrawn
        CreditProductType.CREDIT_LINE: 0.75,    # Partially undrawn
        CreditProductType.AUTO_LOAN: 1.0,       # Fully drawn
    }

    def __init__(self, lgd_params: LGDParameters) -> None:
        self._lgd_params = lgd_params

    def calculate_client_loss(
        self,
        positions: list[CreditPosition],
        probability_of_default: float,
    ) -> ClientLossEstimate:
        """
        Calculate expected loss for a client across all positions.

        Args:
            positions: All credit positions for the client.
            probability_of_default: Client-level PD.

        Returns:
            Aggregated loss estimate with per-position breakdown.
        """
        if not positions:
            return ClientLossEstimate(
                client_id="",
                total_ead=0.0,
                weighted_lgd=0.0,
                total_expected_loss=0.0,
                position_losses=[],
            )

        client_id = positions[0].client_id
        position_losses: list[LossEstimate] = []
        total_ead = 0.0
        total_el = 0.0
        ead_lgd_sum = 0.0  # For weighted LGD calculation

        for position in positions:
            lgd = self._estimate_lgd(position)
            ead = self._estimate_ead(position)
            el = probability_of_default * lgd * ead

            position_losses.append(
                LossEstimate(
                    position_id=position.position_id,
                    product_type=position.product_type,
                    lgd=round(lgd, 4),
                    ead=round(ead, 2),
                    expected_loss=round(el, 2),
                )
            )

            total_ead += ead
            total_el += el
            ead_lgd_sum += ead * lgd

        weighted_lgd = ead_lgd_sum / total_ead if total_ead > 0 else 0.0

        return ClientLossEstimate(
            client_id=client_id,
            total_ead=round(total_ead, 2),
            weighted_lgd=round(weighted_lgd, 4),
            total_expected_loss=round(total_el, 2),
            position_losses=position_losses,
        )

    def _estimate_lgd(self, position: CreditPosition) -> float:
        """
        Estimate Loss Given Default for a single position.

        Uses product-specific base LGD with adjustments for:
        - Collateral coverage (secured positions)
        - Restructuring history
        - Current delinquency severity
        """
        # Base LGD by product type
        base_lgd = self._get_base_lgd(position.product_type)

        # Collateral adjustment for secured positions
        if position.is_secured and position.collateral_value > 0:
            ltv = position.loan_to_value
            if ltv is not None:
                # Lower LTV → better collateral coverage → lower LGD
                if ltv <= 0.60:
                    collateral_adj = -0.15
                elif ltv <= 0.80:
                    collateral_adj = -0.08
                elif ltv <= 1.0:
                    collateral_adj = -0.03
                else:
                    collateral_adj = 0.05  # Underwater: higher LGD
                base_lgd = max(0.05, base_lgd + collateral_adj)

        # Restructuring adjustment (+10% if restructured)
        if position.restructured:
            base_lgd = min(0.95, base_lgd + 0.10)

        # Delinquency severity adjustment
        if position.payment_status == PaymentStatus.DEFAULT:
            base_lgd = min(0.95, base_lgd + 0.05)
        elif position.payment_status in (
            PaymentStatus.DAYS_90,
            PaymentStatus.DAYS_120_PLUS,
        ):
            base_lgd = min(0.95, base_lgd + 0.03)

        return max(0.05, min(base_lgd, 0.95))

    def _get_base_lgd(self, product_type: CreditProductType) -> float:
        """Get base LGD for a product type from configuration."""
        lgd_map: dict[CreditProductType, float] = {
            CreditProductType.MORTGAGE: self._lgd_params.mortgage_secured,
            CreditProductType.PERSONAL_LOAN: self._lgd_params.personal_loan,
            CreditProductType.CREDIT_CARD: self._lgd_params.credit_card,
            CreditProductType.CREDIT_LINE: self._lgd_params.credit_line,
            CreditProductType.AUTO_LOAN: self._lgd_params.auto_loan,
        }
        return lgd_map.get(product_type, self._lgd_params.default)

    def _estimate_ead(self, position: CreditPosition) -> float:
        """
        Estimate Exposure at Default for a single position.

        For amortizing products: EAD = outstanding balance.
        For revolving products: EAD = drawn + CCF × undrawn.
        """
        outstanding = position.outstanding_balance
        ccf = self._CCF.get(position.product_type, 1.0)

        if position.product_type in (
            CreditProductType.CREDIT_CARD,
            CreditProductType.CREDIT_LINE,
        ):
            # Revolving: include potential future drawdown
            undrawn = max(0, position.credit_limit - outstanding)
            ead = outstanding + ccf * undrawn
        else:
            # Amortizing: EAD is current outstanding
            ead = outstanding

        return max(0.0, ead)
