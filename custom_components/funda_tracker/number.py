"""Number platform for Funda Tracker: the amounts the finance sensors build on."""

from __future__ import annotations

import logging

from homeassistant.components.number import NumberEntity, NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, FINANCE_INPUTS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Funda Tracker finance inputs."""
    store = hass.data[DOMAIN][entry.entry_id]["finance"]
    async_add_entities(
        FundaFinanceInput(store, entry, key, name, icon)
        for key, name, icon in FINANCE_INPUTS
    )


class FundaFinanceInput(RestoreNumber, NumberEntity):
    """An amount the user maintains, by hand or from an automation."""

    _attr_has_entity_name = True
    _attr_native_min_value = 0
    _attr_native_max_value = 5_000_000
    _attr_native_step = 1000
    _attr_native_unit_of_measurement = "EUR"
    _attr_mode = NumberMode.BOX

    def __init__(self, store, entry, key, name, icon):
        """Initialise the input."""
        self._store = store
        self._key = key
        self._attr_unique_id = f"funda_tracker_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_value = 0.0
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Funda Tracker",
            manufacturer="Funda",
            model="Waardecheck",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Restore the amount and publish it to the finance store."""
        await super().async_added_to_hass()
        last_number_data = await self.async_get_last_number_data()
        if last_number_data and last_number_data.native_value is not None:
            self._attr_native_value = last_number_data.native_value
        self._store.set(self._key, self._attr_native_value)

    async def async_set_native_value(self, value: float) -> None:
        """Store a new amount and refresh anything derived from it."""
        self._attr_native_value = value
        self._store.set(self._key, value)
        self.async_write_ha_state()
