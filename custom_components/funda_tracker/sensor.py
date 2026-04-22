"""Sensor platform for Funda Tracker."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Sensor definitions: (key suffix in JSON, unique_id_suffix, name, unit, icon, device_class, state_class)
SENSOR_TYPES: list[tuple[str, str, str, str | None, str, SensorDeviceClass | None, SensorStateClass | None]] = [
    ("sensor.funda_house_value", "house_value", "Woningwaarde", "EUR", "mdi:home-analytics", SensorDeviceClass.MONETARY, SensorStateClass.MEASUREMENT),
    ("sensor.funda_ondergrens", "ondergrens", "Ondergrens", "EUR", "mdi:arrow-collapse-down", SensorDeviceClass.MONETARY, SensorStateClass.MEASUREMENT),
    ("sensor.funda_bovengrens", "bovengrens", "Bovengrens", "EUR", "mdi:arrow-collapse-up", SensorDeviceClass.MONETARY, SensorStateClass.MEASUREMENT),
    ("sensor.funda_maandwijziging", "maandwijziging", "Maandwijziging", "EUR", "mdi:trending-up", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_maandwijziging_pct", "maandwijziging_pct", "Maandwijziging %", "%", "mdi:percent", None, None),
    ("sensor.funda_jaarwijziging", "jaarwijziging", "Jaarwijziging", "EUR", "mdi:chart-line", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_jaarwijziging_pct", "jaarwijziging_pct", "Jaarwijziging %", "%", "mdi:percent", None, None),
    ("sensor.funda_all_time_high", "all_time_high", "All-Time High", "EUR", "mdi:arrow-up-bold", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_all_time_low", "all_time_low", "All-Time Low", "EUR", "mdi:arrow-down-bold", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_betrouwbaarheid", "betrouwbaarheid", "Betrouwbaarheid", None, "mdi:shield-check", None, None),
    ("sensor.funda_prijs_per_m2", "prijs_per_m2", "Prijs per m²", "EUR/m²", "mdi:ruler-square", None, None),
    ("sensor.funda_delta_status", "delta_status", "Delta Status", None, "mdi:arrow-up-down", None, None),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Funda Tracker sensors from a config entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        FundaSensor(coordinator, entry, sensor_def)
        for sensor_def in SENSOR_TYPES
    ]
    async_add_entities(entities)


class FundaSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """A Funda Tracker sensor that persists state across HA restarts."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, sensor_def):
        """Initialise the sensor."""
        super().__init__(coordinator)
        json_key, uid_suffix, name, unit, icon, device_class, state_class = sensor_def
        self._json_key = json_key
        self._attr_unique_id = f"funda_tracker_{uid_suffix}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Funda Tracker",
            manufacturer="Funda",
            model="Waardecheck",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._restored_state = None
        self._restored_attrs = {}

    async def async_added_to_hass(self) -> None:
        """Restore last known state when HA starts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._restored_state = last_state.state
            self._restored_attrs = dict(last_state.attributes)

    @property
    def native_value(self):
        """Return the sensor value from coordinator data, or restored state."""
        data = self.coordinator.data or {}
        sensors = data.get("sensors", {})
        sensor = sensors.get(self._json_key)
        if sensor:
            return sensor.get("state")
        return self._restored_state

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes from coordinator data, or restored attributes."""
        data = self.coordinator.data or {}
        sensors = data.get("sensors", {})
        sensor = sensors.get(self._json_key)
        if sensor:
            attrs = dict(sensor.get("attributes", {}))
            # Remove attributes already handled by entity properties
            attrs.pop("unit_of_measurement", None)
            attrs.pop("friendly_name", None)
            attrs.pop("icon", None)
            attrs.pop("state_class", None)
            return attrs
        # Fall back to restored attributes (also cleaned)
        attrs = dict(self._restored_attrs)
        for key in ("unit_of_measurement", "friendly_name", "icon", "state_class",
                     "device_class", "restored"):
            attrs.pop(key, None)
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
