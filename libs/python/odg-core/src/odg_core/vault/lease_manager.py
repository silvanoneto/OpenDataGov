"""Vault lease renewal manager (ADR-073).

Manages automatic renewal of Vault leases for dynamic credentials.
Runs as a background task to ensure credentials don't expire.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from odg_core.vault.client import VaultClient

logger = logging.getLogger(__name__)


class LeaseManager:
    """Manages automatic renewal of Vault leases.

    Monitors active leases and renews them before expiration.
    Typically runs as a background task in the application.

    Example:
        # In application startup
        lease_manager = LeaseManager()
        asyncio.create_task(lease_manager.start())

        # Register a lease
        db_creds = vault.get_database_credentials()
        lease_manager.register_lease(
            lease_id=db_creds["lease_id"],
            lease_duration=db_creds["lease_duration"],
            callback=on_credentials_renewed,
        )

        # In application shutdown
        await lease_manager.stop()
    """

    def __init__(self, vault_client: VaultClient | None = None, renewal_threshold: float = 0.5) -> None:
        """Initialize lease manager.

        Args:
            vault_client: Vault client instance (creates new if None)
            renewal_threshold: Renew when lease has this fraction remaining (default: 0.5 = 50%)
        """
        self._vault = vault_client or VaultClient()
        self._renewal_threshold = renewal_threshold
        self._leases: dict[str, dict[str, Any]] = {}
        self._running = False
        self._task: asyncio.Task[None] | None = None

    def register_lease(
        self,
        lease_id: str,
        lease_duration: int,
        callback: Any = None,
    ) -> None:
        """Register a lease for automatic renewal.

        Args:
            lease_id: Vault lease ID
            lease_duration: Lease duration in seconds
            callback: Optional callback function called after successful renewal
        """
        self._leases[lease_id] = {
            "duration": lease_duration,
            "remaining": lease_duration,
            "callback": callback,
        }
        logger.info("Registered lease %s for renewal (duration: %ds)", lease_id, lease_duration)

    def unregister_lease(self, lease_id: str) -> None:
        """Unregister a lease (stops renewal)."""
        if lease_id in self._leases:
            del self._leases[lease_id]
            logger.info("Unregistered lease %s", lease_id)

    async def start(self) -> None:
        """Start the lease renewal background task."""
        if self._running:
            logger.warning("Lease manager already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._renewal_loop())
        logger.info("Lease manager started")

    async def stop(self) -> None:
        """Stop the lease renewal background task."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("Lease manager stopped")

    async def _renewal_loop(self) -> None:
        """Background loop that monitors and renews leases."""
        while self._running:
            try:
                await self._check_and_renew_leases()
                await asyncio.sleep(30)  # Check every 30 seconds
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in lease renewal loop: %s", e, exc_info=True)
                await asyncio.sleep(30)

    async def _check_and_renew_leases(self) -> None:
        """Check all leases and renew those approaching expiration."""
        for lease_id, lease_info in list(self._leases.items()):
            try:
                # Decrement remaining time
                lease_info["remaining"] -= 30

                # Calculate renewal threshold
                duration = lease_info["duration"]
                threshold = duration * self._renewal_threshold

                # Renew if below threshold
                if lease_info["remaining"] <= threshold:
                    logger.info(
                        "Renewing lease %s (remaining: %ds, threshold: %ds)",
                        lease_id,
                        lease_info["remaining"],
                        threshold,
                    )

                    # Renew the lease
                    result = self._vault.renew_database_lease(lease_id)

                    # Update lease info
                    lease_info["duration"] = result["lease_duration"]
                    lease_info["remaining"] = result["lease_duration"]

                    logger.info(
                        "Lease %s renewed successfully (new duration: %ds)",
                        lease_id,
                        result["lease_duration"],
                    )

                    # Call callback if provided
                    callback = lease_info.get("callback")
                    if callback:
                        try:
                            if asyncio.iscoroutinefunction(callback):
                                await callback(lease_id, result)
                            else:
                                callback(lease_id, result)
                        except Exception as e:
                            logger.error("Error in lease renewal callback: %s", e, exc_info=True)

            except Exception as e:
                logger.error("Failed to renew lease %s: %s", lease_id, e, exc_info=True)

                # If lease renewal fails, try one more time
                if lease_info["remaining"] <= 0:
                    logger.warning("Lease %s has expired, unregistering", lease_id)
                    self.unregister_lease(lease_id)

    def get_lease_info(self, lease_id: str) -> dict[str, Any] | None:
        """Get information about a registered lease."""
        return self._leases.get(lease_id)

    def list_leases(self) -> list[dict[str, Any]]:
        """List all registered leases with their status."""
        return [
            {
                "lease_id": lease_id,
                "duration": info["duration"],
                "remaining": info["remaining"],
                "expiring_soon": info["remaining"] <= info["duration"] * self._renewal_threshold,
            }
            for lease_id, info in self._leases.items()
        ]
