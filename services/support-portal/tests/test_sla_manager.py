"""Tests for SLA Manager - Phase 5.

Tests SLA calculation accuracy, business hours, escalation rules.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from support_portal.models import SupportTier, TicketPriority
from support_portal.sla_manager import SLAManager


@pytest.fixture
def sla_manager():
    """Create SLA manager with mocked DB."""
    db = AsyncMock()
    return SLAManager(db)


class TestSLACalculation:
    """Test SLA target calculations."""

    @pytest.mark.asyncio
    async def test_community_p1_targets(self, sla_manager):
        """Community P1: 4h response, 24h resolution."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            mock_get.return_value = {
                "support_tier": SupportTier.COMMUNITY,
                "priority": TicketPriority.P1_CRITICAL,
                "created_at": datetime(2026, 2, 8, 10, 0, 0),
            }

            response_due, resolution_due = await sla_manager.calculate_sla_targets(
                "tkt_123", SupportTier.COMMUNITY, TicketPriority.P1_CRITICAL
            )

            assert response_due == datetime(2026, 2, 8, 14, 0, 0)  # +4 hours
            assert resolution_due == datetime(2026, 2, 9, 10, 0, 0)  # +24 hours

    @pytest.mark.asyncio
    async def test_professional_business_hours(self, sla_manager):
        """Professional tier uses business hours only."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            # Friday 16:00 (after hours)
            mock_get.return_value = {
                "support_tier": SupportTier.PROFESSIONAL,
                "priority": TicketPriority.P2_HIGH,
                "created_at": datetime(2026, 2, 6, 16, 0, 0),  # Friday 4pm
            }

            response_due, _resolution_due = await sla_manager.calculate_sla_targets(
                "tkt_456", SupportTier.PROFESSIONAL, TicketPriority.P2_HIGH
            )

            # Should skip to Monday 9am + 2 hours = 11am
            assert response_due.weekday() == 0  # Monday
            assert response_due.hour == 11

    @pytest.mark.asyncio
    async def test_enterprise_24_7_coverage(self, sla_manager):
        """Enterprise tier has 24/7 SLA."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            # Sunday 23:00
            mock_get.return_value = {
                "support_tier": SupportTier.ENTERPRISE,
                "priority": TicketPriority.P1_CRITICAL,
                "created_at": datetime(2026, 2, 8, 23, 0, 0),  # Sunday 11pm
            }

            response_due, resolution_due = await sla_manager.calculate_sla_targets(
                "tkt_789", SupportTier.ENTERPRISE, TicketPriority.P1_CRITICAL
            )

            # Should be Sunday 11:30pm (30 minutes later)
            assert response_due == datetime(2026, 2, 8, 23, 30, 0)
            # Resolution: Monday 3am (4 hours later)
            assert resolution_due == datetime(2026, 2, 9, 3, 0, 0)


class TestSLACompliance:
    """Test SLA compliance checking."""

    @pytest.mark.asyncio
    async def test_within_sla(self, sla_manager):
        """Ticket within SLA should show compliant."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            mock_get.return_value = {
                "ticket_id": "tkt_111",
                "support_tier": SupportTier.ENTERPRISE,
                "priority": TicketPriority.P2_HIGH,
                "status": "OPEN",
                "created_at": datetime.utcnow() - timedelta(minutes=30),
                "first_response_at": datetime.utcnow() - timedelta(minutes=15),
                "resolved_at": None,
                "response_sla_target": datetime.utcnow() + timedelta(hours=1),
                "resolution_sla_target": datetime.utcnow() + timedelta(hours=7),
            }

            compliance = await sla_manager.check_sla_compliance("tkt_111")

            assert compliance["response_status"] == "MET"
            assert compliance["resolution_status"] == "ON_TRACK"
            assert compliance["response_elapsed_pct"] < 100
            assert compliance["resolution_elapsed_pct"] < 100

    @pytest.mark.asyncio
    async def test_breached_sla(self, sla_manager):
        """Ticket past SLA should show breach."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            mock_get.return_value = {
                "ticket_id": "tkt_222",
                "support_tier": SupportTier.PROFESSIONAL,
                "priority": TicketPriority.P1_CRITICAL,
                "status": "OPEN",
                "created_at": datetime.utcnow() - timedelta(hours=5),
                "first_response_at": None,  # No response yet
                "resolved_at": None,
                "response_sla_target": datetime.utcnow() - timedelta(hours=1),  # 1h ago
                "resolution_sla_target": datetime.utcnow() + timedelta(hours=3),
            }

            compliance = await sla_manager.check_sla_compliance("tkt_222")

            assert compliance["response_status"] == "BREACHED"
            assert compliance["response_elapsed_pct"] > 100

    @pytest.mark.asyncio
    async def test_resolution_tracking(self, sla_manager):
        """Test resolution time tracking."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            created = datetime.utcnow() - timedelta(hours=20)
            resolved = datetime.utcnow()

            mock_get.return_value = {
                "ticket_id": "tkt_333",
                "support_tier": SupportTier.ENTERPRISE,
                "priority": TicketPriority.P3_NORMAL,
                "status": "SOLVED",
                "created_at": created,
                "first_response_at": created + timedelta(hours=1),
                "resolved_at": resolved,
                "response_sla_target": created + timedelta(hours=2),
                "resolution_sla_target": created + timedelta(hours=24),
            }

            compliance = await sla_manager.check_sla_compliance("tkt_333")

            assert compliance["response_status"] == "MET"
            assert compliance["resolution_status"] == "MET"
            assert compliance["resolution_time_hours"] == 20


class TestEscalation:
    """Test escalation rules."""

    @pytest.mark.asyncio
    async def test_escalation_at_80_percent(self, sla_manager):
        """Escalate at 80% elapsed."""
        with patch.object(sla_manager, "check_sla_compliance") as mock_compliance:
            mock_compliance.return_value = {"response_elapsed_pct": 85.0, "resolution_elapsed_pct": 85.0}

            actions = await sla_manager.check_escalation("tkt_444")

            assert "escalate_to_l2" in actions

    @pytest.mark.asyncio
    async def test_escalation_at_100_percent(self, sla_manager):
        """Escalate to manager at 100% breach."""
        with patch.object(sla_manager, "check_sla_compliance") as mock_compliance:
            mock_compliance.return_value = {"response_elapsed_pct": 105.0, "resolution_elapsed_pct": 105.0}

            actions = await sla_manager.check_escalation("tkt_555")

            assert "notify_manager" in actions
            assert "escalate_to_l2" in actions

    @pytest.mark.asyncio
    async def test_escalation_at_120_percent(self, sla_manager):
        """Critical escalation at 120%."""
        with patch.object(sla_manager, "check_sla_compliance") as mock_compliance:
            mock_compliance.return_value = {"response_elapsed_pct": 125.0, "resolution_elapsed_pct": 125.0}

            actions = await sla_manager.check_escalation("tkt_666")

            assert "notify_director" in actions
            assert "notify_manager" in actions


class TestBusinessHours:
    """Test business hours calculations."""

    @pytest.mark.asyncio
    async def test_skip_weekend(self, sla_manager):
        """Business hours should skip weekends."""
        # Friday 18:00 (6pm)
        start = datetime(2026, 2, 6, 18, 0, 0)  # Friday
        target = sla_manager._add_business_hours(start, hours=2)

        # Should be Monday 11am (9am + 2h)
        assert target.weekday() == 0  # Monday
        assert target.hour == 11

    @pytest.mark.asyncio
    async def test_skip_holidays(self, sla_manager):
        """Business hours should skip holidays."""
        # Assuming Feb 17 is a holiday
        start = datetime(2026, 2, 16, 15, 0, 0)  # Monday 3pm
        target = sla_manager._add_business_hours(start, hours=10)

        # Should skip Tuesday (holiday) and land on Wednesday
        assert target.weekday() == 2  # Wednesday

    @pytest.mark.asyncio
    async def test_multi_day_calculation(self, sla_manager):
        """Business hours across multiple days."""
        start = datetime(2026, 2, 9, 16, 0, 0)  # Monday 4pm
        target = sla_manager._add_business_hours(start, hours=12)

        # 1 hour Monday (4pm-5pm), 8 hours Tuesday, 3 hours Wednesday
        assert target.weekday() == 2  # Wednesday
        assert target.hour == 12  # 12pm (9am + 3h)


class TestFirstResponse:
    """Test first response tracking."""

    @pytest.mark.asyncio
    async def test_record_first_response(self, sla_manager):
        """Recording first response should update ticket."""
        with patch.object(sla_manager.db, "execute") as mock_execute:
            mock_execute.return_value.scalar.return_value = True

            result = await sla_manager.record_first_response("tkt_777")

            assert result is True
            # Verify UPDATE query was called
            mock_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_no_duplicate_first_response(self, sla_manager):
        """Should not overwrite existing first response."""
        with patch.object(sla_manager, "_get_ticket") as mock_get:
            mock_get.return_value = {"first_response_at": datetime.utcnow() - timedelta(hours=1)}

            result = await sla_manager.record_first_response("tkt_888")

            assert result is False  # Already has first response


class TestResolution:
    """Test resolution tracking."""

    @pytest.mark.asyncio
    async def test_record_resolution(self, sla_manager):
        """Recording resolution should calculate time."""
        with patch.object(sla_manager.db, "execute") as mock_execute:
            mock_execute.return_value.scalar.return_value = True

            result = await sla_manager.record_resolution("tkt_999")

            assert result is True

    @pytest.mark.asyncio
    async def test_resolution_time_calculation(self, sla_manager):
        """Resolution time should be created_at to resolved_at."""
        created = datetime.utcnow() - timedelta(hours=15, minutes=30)
        resolved = datetime.utcnow()

        resolution_hours = (resolved - created).total_seconds() / 3600

        assert 15.4 < resolution_hours < 15.6  # ~15.5 hours


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
