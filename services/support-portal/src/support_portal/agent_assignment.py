"""Agent assignment logic for support tickets.

Implements round-robin and skill-based assignment strategies.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from sqlalchemy import and_, func, select
from support_portal.models import (
    ProductArea,
    TicketPriority,
    TicketRow,
    TicketStatus,
    UserRow,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class AgentAssignmentManager:
    """Manages automatic agent assignment for tickets."""

    # Agent skills mapping (product area → required skills)
    SKILL_REQUIREMENTS: ClassVar[dict[ProductArea, list[str]]] = {
        ProductArea.CATALOG: ["data_catalog", "metadata"],
        ProductArea.GOVERNANCE: ["governance", "compliance"],
        ProductArea.QUALITY: ["data_quality", "testing"],
        ProductArea.LINEAGE: ["lineage", "data_pipelines"],
        ProductArea.ML_OPS: ["mlops", "machine_learning"],
        ProductArea.FEDERATION: ["federation", "networking"],
        ProductArea.API: ["api", "integration"],
        ProductArea.SECURITY: ["security", "authentication"],
        ProductArea.BILLING: ["billing", "finance"],
    }

    # Agent availability thresholds
    MAX_OPEN_TICKETS_PER_AGENT: ClassVar[dict[TicketPriority, int]] = {
        TicketPriority.P1_CRITICAL: 2,
        TicketPriority.P2_HIGH: 5,
        TicketPriority.P3_NORMAL: 10,
        TicketPriority.P4_LOW: 15,
    }

    def __init__(self, db: AsyncSession):
        """Initialize assignment manager.

        Args:
            db: Database session
        """
        self.db = db

    async def assign_ticket(
        self,
        ticket_id: str,
        strategy: str = "skill_based",
    ) -> str | None:
        """Assign ticket to best available agent.

        Args:
            ticket_id: Ticket ID to assign
            strategy: Assignment strategy ("skill_based", "round_robin", "load_balanced")

        Returns:
            Assigned agent user_id or None if no agent available
        """
        # Get ticket
        result = await self.db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            logger.error(f"Ticket {ticket_id} not found")
            return None

        if ticket.assigned_to:
            logger.warning(f"Ticket {ticket_id} already assigned to {ticket.assigned_to}")
            return ticket.assigned_to

        # Select strategy
        if strategy == "skill_based":
            agent_id = await self._skill_based_assignment(ticket)
        elif strategy == "round_robin":
            agent_id = await self._round_robin_assignment(ticket)
        elif strategy == "load_balanced":
            agent_id = await self._load_balanced_assignment(ticket)
        else:
            logger.error(f"Unknown assignment strategy: {strategy}")
            return None

        if agent_id:
            # Assign ticket
            ticket.assigned_to = agent_id
            ticket.status = TicketStatus.OPEN.value
            await self.db.commit()

            logger.info(f"✅ Assigned ticket {ticket_id} to agent {agent_id} (strategy: {strategy})")

        return agent_id

    async def _skill_based_assignment(self, ticket: TicketRow) -> str | None:
        """Assign based on agent skills matching product area.

        Args:
            ticket: Ticket to assign

        Returns:
            Agent user_id or None
        """
        product_area = ProductArea(ticket.product_area)
        required_skills = self.SKILL_REQUIREMENTS.get(product_area, [])

        # Get agents with required skills
        # NOTE: Assumes UserRow has a 'skills' JSONB column
        agents_result = await self.db.execute(
            select(UserRow).where(
                and_(
                    UserRow.role == "staff",
                    # UserRow.skills.contains(required_skills),  # PostgreSQL JSONB operator
                )
            )
        )
        skilled_agents = agents_result.scalars().all()

        if not skilled_agents:
            logger.warning(f"No agents with skills {required_skills} found, falling back to any agent")
            # Fallback to any available agent
            return await self._round_robin_assignment(ticket)

        # Among skilled agents, pick least loaded
        priority = TicketPriority(ticket.priority)
        available_agents = []

        for agent in skilled_agents:
            open_tickets = await self._get_agent_open_tickets(agent.user_id)

            max_tickets = self.MAX_OPEN_TICKETS_PER_AGENT.get(
                priority, self.MAX_OPEN_TICKETS_PER_AGENT[TicketPriority.P3_NORMAL]
            )

            if open_tickets < max_tickets:
                available_agents.append((agent.user_id, open_tickets))

        if not available_agents:
            logger.warning(f"All skilled agents at capacity for priority {priority.value}")
            return None

        # Pick agent with least tickets
        available_agents.sort(key=lambda x: x[1])
        return available_agents[0][0]

    async def _round_robin_assignment(self, ticket: TicketRow) -> str | None:
        """Simple round-robin assignment.

        Args:
            ticket: Ticket to assign

        Returns:
            Agent user_id or None
        """
        # Get all staff users
        agents_result = await self.db.execute(select(UserRow).where(UserRow.role == "staff"))
        agents = agents_result.scalars().all()

        if not agents:
            logger.error("No staff agents found")
            return None

        # Get last assigned agent from most recent ticket
        last_assigned_result = await self.db.execute(
            select(TicketRow.assigned_to)
            .where(TicketRow.assigned_to.isnot(None))
            .order_by(TicketRow.created_at.desc())
            .limit(1)
        )
        last_assigned = last_assigned_result.scalar()

        # Find next agent in rotation
        agent_ids = [a.user_id for a in agents]

        if last_assigned and last_assigned in agent_ids:
            # Get next agent after last assigned
            last_index = agent_ids.index(last_assigned)
            next_index = (last_index + 1) % len(agent_ids)
            return agent_ids[next_index]
        else:
            # No previous assignment, start with first agent
            return agent_ids[0]

    async def _load_balanced_assignment(self, ticket: TicketRow) -> str | None:
        """Assign to agent with fewest open tickets.

        Args:
            ticket: Ticket to assign

        Returns:
            Agent user_id or None
        """
        # Get all staff users
        agents_result = await self.db.execute(select(UserRow).where(UserRow.role == "staff"))
        agents = agents_result.scalars().all()

        if not agents:
            logger.error("No staff agents found")
            return None

        # Count open tickets per agent
        agent_loads = []

        for agent in agents:
            open_tickets = await self._get_agent_open_tickets(agent.user_id)
            agent_loads.append((agent.user_id, open_tickets))

        # Sort by load (ascending)
        agent_loads.sort(key=lambda x: x[1])

        # Return agent with least tickets
        return agent_loads[0][0]

    async def _get_agent_open_tickets(self, agent_id: str) -> int:
        """Get count of open tickets for agent.

        Args:
            agent_id: Agent user_id

        Returns:
            Count of open tickets
        """
        result = await self.db.execute(
            select(func.count(TicketRow.ticket_id)).where(
                and_(
                    TicketRow.assigned_to == agent_id,
                    TicketRow.status.in_(
                        [
                            TicketStatus.NEW.value,
                            TicketStatus.OPEN.value,
                            TicketStatus.PENDING.value,
                        ]
                    ),
                )
            )
        )

        return result.scalar() or 0

    async def reassign_ticket(
        self,
        ticket_id: str,
        new_agent_id: str,
        reason: str | None = None,
    ) -> bool:
        """Manually reassign ticket to different agent.

        Args:
            ticket_id: Ticket ID
            new_agent_id: New agent user_id
            reason: Optional reassignment reason

        Returns:
            True if reassigned successfully
        """
        # Get ticket
        result = await self.db.execute(select(TicketRow).where(TicketRow.ticket_id == ticket_id))
        ticket = result.scalars().first()

        if not ticket:
            logger.error(f"Ticket {ticket_id} not found")
            return False

        # Verify new agent exists and is staff
        agent_result = await self.db.execute(
            select(UserRow).where(
                and_(
                    UserRow.user_id == new_agent_id,
                    UserRow.role == "staff",
                )
            )
        )
        agent = agent_result.scalars().first()

        if not agent:
            logger.error(f"Agent {new_agent_id} not found or not staff")
            return False

        old_agent = ticket.assigned_to

        # Reassign
        ticket.assigned_to = new_agent_id
        await self.db.commit()

        logger.info(
            f"✅ Reassigned ticket {ticket_id} from {old_agent} to {new_agent_id} (reason: {reason or 'manual'})"
        )

        return True

    async def get_agent_workload(self, agent_id: str) -> dict[str, Any]:
        """Get agent workload statistics.

        Args:
            agent_id: Agent user_id

        Returns:
            Workload stats
        """
        # Open tickets
        open_tickets = await self._get_agent_open_tickets(agent_id)

        # Tickets by priority
        priority_result = await self.db.execute(
            select(TicketRow.priority, func.count(TicketRow.ticket_id).label("count"))
            .where(
                and_(
                    TicketRow.assigned_to == agent_id,
                    TicketRow.status.in_(
                        [
                            TicketStatus.NEW.value,
                            TicketStatus.OPEN.value,
                            TicketStatus.PENDING.value,
                        ]
                    ),
                )
            )
            .group_by(TicketRow.priority)
        )
        by_priority = {row.priority: row.count for row in priority_result.all()}

        # Tickets resolved today
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        resolved_today_result = await self.db.execute(
            select(func.count(TicketRow.ticket_id)).where(
                and_(
                    TicketRow.assigned_to == agent_id,
                    TicketRow.resolved_at >= today,
                )
            )
        )
        resolved_today = resolved_today_result.scalar() or 0

        # Average response time (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        response_time_result = await self.db.execute(
            select(
                func.avg(func.extract("epoch", TicketRow.first_response_at - TicketRow.created_at)).label(
                    "avg_response_seconds"
                )
            ).where(
                and_(
                    TicketRow.assigned_to == agent_id,
                    TicketRow.first_response_at.isnot(None),
                    TicketRow.created_at >= thirty_days_ago,
                )
            )
        )
        avg_response_seconds = response_time_result.scalar()

        return {
            "agent_id": agent_id,
            "open_tickets": open_tickets,
            "by_priority": by_priority,
            "resolved_today": resolved_today,
            "avg_response_time_seconds": int(avg_response_seconds) if avg_response_seconds else None,
        }

    async def get_team_workload(self) -> list[dict[str, Any]]:
        """Get workload for all agents.

        Returns:
            List of agent workload stats
        """
        # Get all staff
        agents_result = await self.db.execute(select(UserRow).where(UserRow.role == "staff"))
        agents = agents_result.scalars().all()

        workloads = []
        for agent in agents:
            workload = await self.get_agent_workload(agent.user_id)
            workload["agent_name"] = agent.name
            workload["agent_email"] = agent.email
            workloads.append(workload)

        # Sort by open tickets (descending)
        workloads.sort(key=lambda x: x["open_tickets"], reverse=True)

        return workloads
