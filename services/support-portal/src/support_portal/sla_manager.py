"""SLA Manager - Track and enforce SLA compliance."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import and_, select, update
from support_portal.models import (
    OrganizationRow,
    SupportTier,
    TicketPriority,
    TicketRow,
    TicketStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class SLAManager:
    """Manages SLA tracking and enforcement."""

    # SLA targets (first response time)
    SLA_TARGETS: ClassVar[dict[tuple[SupportTier, TicketPriority], timedelta]] = {
        (SupportTier.ENTERPRISE, TicketPriority.P1_CRITICAL): timedelta(hours=4),
        (SupportTier.ENTERPRISE, TicketPriority.P2_HIGH): timedelta(hours=8),
        (SupportTier.ENTERPRISE, TicketPriority.P3_NORMAL): timedelta(hours=24),
        (SupportTier.ENTERPRISE, TicketPriority.P4_LOW): timedelta(hours=48),
        (SupportTier.PROFESSIONAL, TicketPriority.URGENT): timedelta(hours=8),
        (SupportTier.PROFESSIONAL, TicketPriority.HIGH): timedelta(hours=24),
        (SupportTier.PROFESSIONAL, TicketPriority.NORMAL): timedelta(hours=48),
    }

    # Resolution time targets
    RESOLUTION_TARGETS: ClassVar[dict[tuple[SupportTier, TicketPriority], timedelta]] = {
        (SupportTier.ENTERPRISE, TicketPriority.P1_CRITICAL): timedelta(hours=24),
        (SupportTier.ENTERPRISE, TicketPriority.P2_HIGH): timedelta(days=3),
        (SupportTier.ENTERPRISE, TicketPriority.P3_NORMAL): timedelta(days=7),
        (SupportTier.ENTERPRISE, TicketPriority.P4_LOW): timedelta(days=14),
        (SupportTier.PROFESSIONAL, TicketPriority.URGENT): timedelta(days=2),
        (SupportTier.PROFESSIONAL, TicketPriority.HIGH): timedelta(days=5),
        (SupportTier.PROFESSIONAL, TicketPriority.NORMAL): timedelta(days=10),
    }

    # Business hours (for Professional tier)
    BUSINESS_HOURS_START = 9  # 9 AM
    BUSINESS_HOURS_END = 17  # 5 PM
    BUSINESS_DAYS: ClassVar[list[int]] = [0, 1, 2, 3, 4]  # Monday-Friday

    # Escalation rules
    ESCALATION_RULES: ClassVar[dict[tuple[SupportTier, TicketPriority], dict[str, str]]] = {
        (SupportTier.ENTERPRISE, TicketPriority.P1_CRITICAL): {
            "80%": "notify_manager",
            "100%": "escalate_to_vp_engineering",
            "120%": "page_on_call",
        },
        (SupportTier.ENTERPRISE, TicketPriority.P2_HIGH): {
            "80%": "notify_manager",
            "100%": "escalate_to_director",
        },
        (SupportTier.ENTERPRISE, TicketPriority.P3_NORMAL): {
            "100%": "notify_manager",
        },
        (SupportTier.PROFESSIONAL, TicketPriority.URGENT): {
            "100%": "notify_manager",
        },
    }

    def __init__(self, db: AsyncSession):
        """Initialize SLA manager.

        Args:
            db: Database session
        """
        self.db = db

    async def calculate_sla_targets(
        self, ticket_id: str, tier: SupportTier, priority: TicketPriority
    ) -> tuple[datetime, datetime]:
        """Calculate SLA target times for a ticket.

        Args:
            ticket_id: Ticket ID
            tier: Support tier
            priority: Ticket priority

        Returns:
            Tuple of (first_response_target, resolution_target)
        """
        result = await self.db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        created_at = ticket.created_at

        # Get SLA targets
        response_sla = self.SLA_TARGETS.get((tier, priority))
        resolution_sla = self.RESOLUTION_TARGETS.get((tier, priority))

        if not response_sla:
            logger.warning(f"No SLA defined for {tier}/{priority}")
            return None, None

        # Calculate targets
        if tier == SupportTier.PROFESSIONAL:
            # Account for business hours
            response_target = self._add_business_hours(created_at, response_sla)
            resolution_target = self._add_business_hours(created_at, resolution_sla)
        else:
            # Enterprise P1 is 24/7
            response_target = created_at + response_sla
            resolution_target = created_at + resolution_sla

        logger.info(f"Ticket {ticket_id} SLA: First response by {response_target}, Resolution by {resolution_target}")

        return response_target, resolution_target

    def _add_business_hours(self, start_time: datetime, duration: timedelta) -> datetime:
        """Add business hours to a start time.

        Args:
            start_time: Start time
            duration: Duration to add (business hours only)

        Returns:
            Target datetime
        """
        hours_to_add = duration.total_seconds() / 3600
        current_time = start_time
        hours_added = 0

        while hours_added < hours_to_add:
            # Skip weekends
            if current_time.weekday() not in self.BUSINESS_DAYS:
                current_time += timedelta(days=1)
                current_time = current_time.replace(hour=self.BUSINESS_HOURS_START, minute=0, second=0)
                continue

            # Skip non-business hours
            if current_time.hour < self.BUSINESS_HOURS_START:
                current_time = current_time.replace(hour=self.BUSINESS_HOURS_START, minute=0, second=0)
            elif current_time.hour >= self.BUSINESS_HOURS_END:
                current_time += timedelta(days=1)
                current_time = current_time.replace(hour=self.BUSINESS_HOURS_START, minute=0, second=0)
                continue

            # Add 1 hour
            current_time += timedelta(hours=1)
            hours_added += 1

        return current_time

    async def check_sla_compliance(self, ticket_id: str) -> dict[str, Any]:
        """Check SLA compliance for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            SLA compliance status
        """
        result = await self.db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        # Get organization tier
        org_result = await self.db.execute(select(OrganizationRow).where(OrganizationRow.org_id == ticket.org_id))
        org = org_result.scalars().first()

        if not org:
            raise ValueError(f"Organization {ticket.org_id} not found")

        tier = SupportTier(org.support_tier)
        priority = TicketPriority(ticket.priority)

        # Calculate elapsed times
        now = datetime.utcnow()
        time_since_creation = now - ticket.created_at

        first_response_time = ticket.first_response_at - ticket.created_at if ticket.first_response_at else None

        resolution_time = ticket.resolved_at - ticket.created_at if ticket.resolved_at else None

        # Get SLA targets
        response_target, resolution_target = await self.calculate_sla_targets(ticket_id, tier, priority)

        if not response_target:
            return {"sla_applicable": False}

        # Check compliance
        first_response_compliant = ticket.first_response_at is not None and first_response_time <= (
            response_target - ticket.created_at
        )

        resolution_compliant = ticket.resolved_at is not None and resolution_time <= (
            resolution_target - ticket.created_at
        )

        # Calculate percentage of SLA elapsed
        if ticket.first_response_at is None:
            response_sla_elapsed_pct = time_since_creation / (response_target - ticket.created_at) * 100
        else:
            response_sla_elapsed_pct = 100.0  # Already responded

        if ticket.resolved_at is None:
            resolution_sla_elapsed_pct = time_since_creation / (resolution_target - ticket.created_at) * 100
        else:
            resolution_sla_elapsed_pct = 100.0  # Already resolved

        return {
            "sla_applicable": True,
            "tier": tier.value,
            "priority": priority.value,
            "response_target": response_target,
            "resolution_target": resolution_target,
            "first_response_at": ticket.first_response_at,
            "resolved_at": ticket.resolved_at,
            "first_response_compliant": first_response_compliant,
            "resolution_compliant": resolution_compliant,
            "response_sla_elapsed_pct": response_sla_elapsed_pct,
            "resolution_sla_elapsed_pct": resolution_sla_elapsed_pct,
            "sla_breached": ticket.sla_breached,
        }

    async def check_escalation(self, ticket_id: str) -> list[str]:
        """Check if ticket needs escalation.

        Args:
            ticket_id: Ticket ID

        Returns:
            List of escalation actions needed
        """
        compliance = await self.check_sla_compliance(ticket_id)

        if not compliance["sla_applicable"]:
            return []

        tier = SupportTier(compliance["tier"])
        priority = TicketPriority(compliance["priority"])
        elapsed_pct = compliance["response_sla_elapsed_pct"]

        # Get escalation rules
        escalation_rules = self.ESCALATION_RULES.get((tier, priority), {})

        actions = []
        for threshold_str, action in escalation_rules.items():
            threshold_pct = int(threshold_str.rstrip("%"))

            if elapsed_pct >= threshold_pct:
                actions.append(action)
                logger.warning(f"Ticket {ticket_id} SLA {elapsed_pct:.1f}% elapsed, triggering escalation: {action}")

        return actions

    async def record_first_response(self, ticket_id: str) -> bool:
        """Record first response time for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            True if recorded successfully
        """
        now = datetime.utcnow()

        result = await self.db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        if ticket.first_response_at:
            logger.warning(f"Ticket {ticket_id} already has first response recorded")
            return False

        # Update ticket
        await self.db.execute(update(TicketRow).where(TicketRow.ticket_id == ticket_id).values(first_response_at=now))
        await self.db.commit()

        # Check SLA compliance
        compliance = await self.check_sla_compliance(ticket_id)

        if compliance["sla_applicable"]:
            response_time = now - ticket.created_at
            target_time = compliance["response_target"] - ticket.created_at

            if response_time <= target_time:
                logger.info(f"✅ Ticket {ticket_id} first response within SLA: {response_time} <= {target_time}")
            else:
                logger.warning(f"⚠️  Ticket {ticket_id} first response SLA BREACHED: {response_time} > {target_time}")

                # Mark as SLA breached
                await self.db.execute(
                    update(TicketRow).where(TicketRow.ticket_id == ticket_id).values(sla_breached=True)
                )
                await self.db.commit()

        return True

    async def record_resolution(self, ticket_id: str) -> bool:
        """Record resolution time for a ticket.

        Args:
            ticket_id: Ticket ID

        Returns:
            True if recorded successfully
        """
        now = datetime.utcnow()

        result = await self.db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            raise ValueError(f"Ticket {ticket_id} not found")

        if ticket.resolved_at:
            logger.warning(f"Ticket {ticket_id} already resolved")
            return False

        # Update ticket
        await self.db.execute(
            update(TicketRow)
            .where(TicketRow.ticket_id == ticket_id)
            .values(resolved_at=now, status=TicketStatus.SOLVED.value)
        )
        await self.db.commit()

        # Check SLA compliance
        compliance = await self.check_sla_compliance(ticket_id)

        if compliance["sla_applicable"]:
            resolution_time = now - ticket.created_at
            target_time = compliance["resolution_target"] - ticket.created_at

            if resolution_time <= target_time:
                logger.info(f"✅ Ticket {ticket_id} resolved within SLA: {resolution_time} <= {target_time}")
            else:
                logger.warning(f"⚠️  Ticket {ticket_id} resolution SLA BREACHED: {resolution_time} > {target_time}")

                # Mark as SLA breached (if not already)
                await self.db.execute(
                    update(TicketRow).where(TicketRow.ticket_id == ticket_id).values(sla_breached=True)
                )
                await self.db.commit()

        return True

    async def get_sla_metrics(self, tier: SupportTier | None = None) -> dict[str, Any]:
        """Get SLA compliance metrics.

        Args:
            tier: Filter by support tier (optional)

        Returns:
            SLA metrics
        """
        query = select(TicketRow)

        if tier:
            # Join with organizations to filter by tier
            query = query.join(OrganizationRow, TicketRow.org_id == OrganizationRow.org_id).where(
                OrganizationRow.support_tier == tier.value
            )

        result = await self.db.execute(query)
        tickets = result.scalars().all()

        total_tickets = len(tickets)
        if total_tickets == 0:
            return {"total_tickets": 0}

        # Calculate metrics
        tickets_with_first_response = [t for t in tickets if t.first_response_at]
        tickets_resolved = [t for t in tickets if t.resolved_at]
        tickets_sla_breached = [t for t in tickets if t.sla_breached]

        # First response metrics
        first_response_times = [
            (t.first_response_at - t.created_at).total_seconds() for t in tickets_with_first_response
        ]

        avg_first_response = sum(first_response_times) / len(first_response_times) if first_response_times else None

        # Resolution metrics
        resolution_times = [(t.resolved_at - t.created_at).total_seconds() for t in tickets_resolved]

        avg_resolution_time = sum(resolution_times) / len(resolution_times) if resolution_times else None

        # SLA compliance
        sla_compliance_rate = (total_tickets - len(tickets_sla_breached)) / total_tickets * 100

        return {
            "total_tickets": total_tickets,
            "first_response_rate": len(tickets_with_first_response) / total_tickets * 100,
            "resolution_rate": len(tickets_resolved) / total_tickets * 100,
            "sla_compliance_rate": sla_compliance_rate,
            "avg_first_response_seconds": avg_first_response,
            "avg_resolution_seconds": avg_resolution_time,
            "sla_breached_count": len(tickets_sla_breached),
        }

    async def monitor_sla_breaches(self) -> list[dict[str, Any]]:
        """Monitor tickets approaching SLA breach.

        Returns:
            List of tickets at risk
        """
        # Get all open tickets
        result = await self.db.execute(
            select(TicketRow).where(
                and_(
                    TicketRow.status.in_([TicketStatus.NEW.value, TicketStatus.OPEN.value]),
                    TicketRow.first_response_at.is_(None),
                )
            )
        )
        open_tickets = result.scalars().all()

        at_risk = []

        for ticket in open_tickets:
            compliance = await self.check_sla_compliance(ticket.ticket_id)

            if not compliance["sla_applicable"]:
                continue

            elapsed_pct = compliance["response_sla_elapsed_pct"]

            # Flag tickets > 80% SLA elapsed
            if elapsed_pct >= 80:
                escalation_actions = await self.check_escalation(ticket.ticket_id)

                at_risk.append(
                    {
                        "ticket_id": ticket.ticket_id,
                        "subject": ticket.subject,
                        "priority": ticket.priority,
                        "sla_elapsed_pct": elapsed_pct,
                        "response_target": compliance["response_target"],
                        "escalation_actions": escalation_actions,
                    }
                )

        return at_risk
