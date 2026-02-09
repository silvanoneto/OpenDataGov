"""Budget Monitor - Tracks budget consumption and sends alerts.

Monitors budgets in real-time, calculates burn rate, forecasts exhaustion date,
and sends alerts when thresholds are exceeded.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from finops_dashboard.models import (
    BudgetPeriod,
    BudgetRow,
    BudgetStatus,
    BudgetStatusHistoryRow,
    CloudCostRow,
)
from sqlalchemy import func, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class BudgetMonitor:
    """Monitors budgets and sends alerts."""

    def __init__(self, db: AsyncSession):
        """Initialize budget monitor.

        Args:
            db: Database session
        """
        self.db = db

    async def check_all_budgets(self) -> list[BudgetStatus]:
        """Check all active budgets and return their status.

        Returns:
            List of budget statuses
        """
        # Get all active budgets
        result = await self.db.execute(select(BudgetRow).where(BudgetRow.active))
        budgets = result.scalars().all()

        budget_statuses = []

        for budget in budgets:
            status = await self.get_budget_status(budget.budget_id)
            budget_statuses.append(status)

            # Check if alerts should be triggered
            await self._check_and_send_alerts(budget, status)

        return budget_statuses

    async def get_budget_status(self, budget_id: int) -> BudgetStatus:
        """Get current status for a budget.

        Args:
            budget_id: Budget ID

        Returns:
            Current budget status
        """
        # Get budget
        result = await self.db.execute(select(BudgetRow).where(BudgetRow.budget_id == budget_id))
        budget = result.scalar_one()

        # Calculate period dates
        period_start, period_end = self._get_period_dates(budget.period)

        # Calculate spend to date
        spent_to_date = await self._calculate_spend(
            budget.scope_type,
            budget.scope_value,
            period_start,
            datetime.utcnow(),
        )

        # Calculate metrics
        remaining = budget.amount - spent_to_date
        pct_consumed = (spent_to_date / budget.amount * 100) if budget.amount > 0 else 0

        # Calculate burn rate (daily average)
        days_elapsed = (datetime.utcnow() - period_start).days
        burn_rate_per_day = spent_to_date / days_elapsed if days_elapsed > 0 else Decimal(0)

        # Forecast exhaustion date
        forecast_exhaustion_date = None
        if burn_rate_per_day > 0 and remaining > 0:
            days_until_exhaustion = int(remaining / burn_rate_per_day)
            forecast_exhaustion_date = datetime.utcnow() + timedelta(days=days_until_exhaustion)

        # Determine if on track
        days_in_period = (period_end - period_start).days
        expected_pct = (days_elapsed / days_in_period * 100) if days_in_period > 0 else 0
        on_track = pct_consumed <= (expected_pct + 10)  # 10% tolerance

        # Determine alert level
        alert_level = self._get_alert_level(pct_consumed, budget.alert_thresholds)

        status = BudgetStatus(
            budget_id=budget.budget_id,
            budget_name=budget.budget_name,
            amount=budget.amount,
            spent_to_date=spent_to_date,
            remaining=remaining,
            pct_consumed=Decimal(pct_consumed),
            burn_rate_per_day=burn_rate_per_day,
            forecast_exhaustion_date=forecast_exhaustion_date,
            on_track=on_track,
            alert_level=alert_level,
        )

        # Save status history
        await self._save_status_history(budget_id, status)

        return status

    async def _calculate_spend(
        self,
        scope_type: str,
        scope_value: str | None,
        start_date: datetime,
        end_date: datetime,
    ) -> Decimal:
        """Calculate total spend for a scope and time period.

        Args:
            scope_type: organization, project, team, service, environment
            scope_value: Value for the scope (or None for organization-wide)
            start_date: Start date
            end_date: End date

        Returns:
            Total spend
        """
        query = select(func.sum(CloudCostRow.cost)).where(
            CloudCostRow.time >= start_date,
            CloudCostRow.time <= end_date,
        )

        # Add scope filter
        if scope_type == "project" and scope_value:
            query = query.where(CloudCostRow.project == scope_value)
        elif scope_type == "team" and scope_value:
            query = query.where(CloudCostRow.team == scope_value)
        elif scope_type == "service" and scope_value:
            query = query.where(CloudCostRow.service == scope_value)
        elif scope_type == "environment" and scope_value:
            query = query.where(CloudCostRow.environment == scope_value)
        # organization-wide: no filter

        result = await self.db.execute(query)
        total_spend = result.scalar() or Decimal(0)

        return total_spend

    def _get_period_dates(self, period: str) -> tuple[datetime, datetime]:
        """Get start and end dates for budget period.

        Args:
            period: Budget period (monthly, quarterly, yearly)

        Returns:
            Tuple of (start_date, end_date)
        """
        now = datetime.utcnow()

        if period == BudgetPeriod.MONTHLY:
            # First day of current month
            start_date = datetime(now.year, now.month, 1)
            # First day of next month
            end_date = datetime(now.year + 1, 1, 1) if now.month == 12 else datetime(now.year, now.month + 1, 1)

        elif period == BudgetPeriod.QUARTERLY:
            # First day of current quarter
            quarter = (now.month - 1) // 3 + 1
            start_month = (quarter - 1) * 3 + 1
            start_date = datetime(now.year, start_month, 1)

            # First day of next quarter
            end_month = start_month + 3
            end_date = datetime(now.year + 1, end_month - 12, 1) if end_month > 12 else datetime(now.year, end_month, 1)

        else:  # YEARLY
            # First day of current year
            start_date = datetime(now.year, 1, 1)
            # First day of next year
            end_date = datetime(now.year + 1, 1, 1)

        return start_date, end_date

    def _get_alert_level(self, pct_consumed: float, thresholds: list[int] | None) -> str:
        """Determine alert level based on percentage consumed.

        Args:
            pct_consumed: Percentage of budget consumed
            thresholds: Alert thresholds (e.g., [50, 80, 100, 120])

        Returns:
            Alert level: green, yellow, orange, red
        """
        if not thresholds:
            thresholds = [50, 80, 100, 120]

        if pct_consumed < thresholds[0]:
            return "green"
        elif pct_consumed < thresholds[1]:
            return "yellow"
        elif pct_consumed < thresholds[2]:
            return "orange"
        else:
            return "red"

    async def _check_and_send_alerts(self, budget: BudgetRow, status: BudgetStatus):
        """Check if alerts should be sent based on thresholds.

        Args:
            budget: Budget configuration
            status: Current budget status
        """
        thresholds = budget.alert_thresholds or [50, 80, 100, 120]

        for threshold in thresholds:
            # Check if threshold just crossed
            if status.pct_consumed >= threshold:
                # Check if alert already sent for this threshold
                # (Implementation would query alert history table)

                # Send alert
                await self._send_budget_alert(budget, status, threshold)

    async def _send_budget_alert(self, budget: BudgetRow, status: BudgetStatus, threshold: int):
        """Send budget alert via configured channels.

        Args:
            budget: Budget configuration
            status: Current budget status
            threshold: Threshold that triggered alert
        """
        alert_channels = budget.alert_channels or {}

        # Build alert message
        message = self._build_alert_message(budget, status, threshold)

        # Send to Slack
        if alert_channels.get("slack"):
            await self._send_slack_alert(alert_channels["slack"], message)

        # Send email
        if alert_channels.get("email"):
            for email in alert_channels["email"]:
                await self._send_email_alert(email, f"Budget Alert: {budget.budget_name}", message)

        # Send to PagerDuty (for critical alerts only)
        if alert_channels.get("pagerduty") and threshold >= 100:
            await self._send_pagerduty_alert(budget.budget_name, message)

        logger.info(f"Sent budget alert for {budget.budget_name}: {threshold}% threshold crossed")

    def _build_alert_message(self, budget: BudgetRow, status: BudgetStatus, threshold: int) -> str:
        """Build formatted alert message.

        Args:
            budget: Budget configuration
            status: Current budget status
            threshold: Threshold that triggered alert

        Returns:
            Formatted alert message
        """
        emoji = "🟡" if threshold < 80 else "🟠" if threshold < 100 else "🔴"

        message = f"""
{emoji} **Budget Alert: {budget.budget_name}**

**Threshold:** {threshold}% exceeded
**Budget:** ${budget.amount:,.2f} / {budget.period}
**Spent:** ${status.spent_to_date:,.2f} ({status.pct_consumed:.1f}%)
**Remaining:** ${status.remaining:,.2f}

**Burn Rate:** ${status.burn_rate_per_day:,.2f} / day
"""

        if status.forecast_exhaustion_date and status.forecast_exhaustion_date < datetime.utcnow() + timedelta(days=30):
            days_until = (status.forecast_exhaustion_date - datetime.utcnow()).days
            exhaust_date = status.forecast_exhaustion_date.strftime("%Y-%m-%d")
            message += f"\n⚠️ **Forecast:** Budget will be exhausted in {days_until} days ({exhaust_date})\n"

        message += f"\n**Scope:** {budget.scope_type.capitalize()}"
        if budget.scope_value:
            message += f" = {budget.scope_value}"

        message += "\n\n**Action:** Review top spenders in FinOps dashboard"

        return message

    async def _send_slack_alert(self, channel: str, message: str):
        """Send alert to Slack.

        Args:
            channel: Slack channel
            message: Alert message
        """
        # Implementation would use Slack SDK
        logger.info(f"Would send Slack alert to {channel}: {message[:100]}...")

    async def _send_email_alert(self, email: str, subject: str, body: str):
        """Send alert email.

        Args:
            email: Recipient email
            subject: Email subject
            body: Email body
        """
        # Implementation would use SendGrid
        logger.info(f"Would send email to {email}: {subject}")

    async def _send_pagerduty_alert(self, budget_name: str, message: str):
        """Send alert to PagerDuty.

        Args:
            budget_name: Budget name
            message: Alert message
        """
        # Implementation would use PagerDuty Events API
        logger.info(f"Would send PagerDuty alert for {budget_name}")

    async def _save_status_history(self, budget_id: int, status: BudgetStatus):
        """Save budget status to history table.

        Args:
            budget_id: Budget ID
            status: Budget status
        """
        history = BudgetStatusHistoryRow(
            budget_id=budget_id,
            snapshot_date=datetime.utcnow(),
            spent_to_date=status.spent_to_date,
            remaining=status.remaining,
            pct_consumed=status.pct_consumed,
            burn_rate_per_day=status.burn_rate_per_day,
            forecast_exhaustion_date=status.forecast_exhaustion_date,
        )

        self.db.add(history)
        await self.db.commit()
