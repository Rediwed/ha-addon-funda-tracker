"""Funda Tracker integration — reads scraped house value data from the add-on."""

import json
import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, SCAN_INTERVAL_MINUTES, SENSOR_DATA_PATH

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

    async def _async_update_data(self) -> dict:
        """Read sensor data from the shared JSON file."""
        return await self.hass.async_add_executor_job(self._read_data)

    def _read_data(self) -> dict:
        if not self._path.exists():
            _LOGGER.debug("Sensor data file not found at %s", self._path)
            return {}
        try:
            with open(self._path) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            _LOGGER.warning("Failed to read sensor data: %s", exc)
            return {}
