"""Funda Tracker integration — reads scraped house value data from the add-on."""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL_MINUTES, SENSOR_DATA_PATH, STALE_DATA_AFTER

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Funda Tracker from a config entry."""
    coordinator = FundaDataCoordinator(hass)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


class FundaDataCoordinator(DataUpdateCoordinator):
    """Coordinator that reads sensor data from the shared JSON file."""

    def __init__(self, hass: HomeAssistant) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=SCAN_INTERVAL_MINUTES),
        )
        self._path = Path(SENSOR_DATA_PATH)
        self._data_issue: str | None = None
        self.last_successful_update: datetime | None = None
        self.update_overdue = True

    async def _async_update_data(self) -> dict:
        """Read sensor data from the shared JSON file."""
        previous_data = self.data if isinstance(self.data, dict) else {}
        return await self.hass.async_add_executor_job(self._read_data, previous_data)

    def _read_data(self, previous_data: dict) -> dict:
        if not self._path.exists():
            self._log_data_issue(
                "missing",
                "Sensor data file not found at %s; keeping restored sensor values",
                self._path,
            )
            self._refresh_overdue_status()
            return previous_data
        try:
            with open(self._path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            self._log_data_issue("unreadable", "Failed to read sensor data: %s", exc)
            self._refresh_overdue_status()
            return previous_data

        if not isinstance(data, dict) or not isinstance(data.get("sensors"), dict):
            self._log_data_issue(
                "invalid_data",
                "Sensor data does not contain a valid sensors object",
            )
            self._refresh_overdue_status()
            return previous_data

        last_updated = data.get("last_updated")
        try:
            updated_at = datetime.fromisoformat(last_updated)
        except (TypeError, ValueError):
            self._log_data_issue(
                "invalid_timestamp",
                "Sensor data has no valid last_updated timestamp",
            )
            self._refresh_overdue_status()
            return previous_data

        self.last_successful_update = updated_at
        now = datetime.now(updated_at.tzinfo)
        self.update_overdue = now - updated_at > STALE_DATA_AFTER
        if self.update_overdue:
            self._log_data_issue(
                "stale",
                "Sensor data has not been refreshed since %s",
                last_updated,
            )
        elif self._data_issue is not None:
            _LOGGER.info("Funda Tracker sensor data is available again")
            self._data_issue = None

        return data

    def _refresh_overdue_status(self) -> None:
        """Recalculate freshness while retaining the last valid payload."""
        if self.last_successful_update is None:
            self.update_overdue = True
            return
        now = datetime.now(self.last_successful_update.tzinfo)
        self.update_overdue = now - self.last_successful_update > STALE_DATA_AFTER

    def _log_data_issue(self, issue: str, message: str, *args) -> None:
        """Log a data issue once until its type changes or data recovers."""
        if issue == self._data_issue:
            return
        self._data_issue = issue
        _LOGGER.warning(message, *args)
