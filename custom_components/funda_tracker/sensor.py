"""Sensor platform for Funda Tracker."""

from __future__ import annotations

import logging
from datetime import datetime

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
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

from .const import DOMAIN, FINANCE_SENSORS, STALE_DATA_AFTER

_LOGGER = logging.getLogger(__name__)

HOUSE_VALUE_KEY = "sensor.funda_house_value"

# Object ids are pinned so the entity_id never picks up the device's area as a
# prefix. The _2 suffixes are historic and kept so existing dashboards survive.
# (key suffix in JSON, unique_id_suffix, object id suffix, name, unit, icon, device_class, state_class)
SENSOR_TYPES: list[tuple[str, str, str, str, str | None, str, SensorDeviceClass | None, SensorStateClass | None]] = [
    ("sensor.funda_house_value", "house_value", "woningwaarde", "Woningwaarde", "EUR", "mdi:home-analytics", SensorDeviceClass.MONETARY, SensorStateClass.MEASUREMENT),
    ("sensor.funda_ondergrens", "ondergrens", "ondergrens", "Ondergrens", "EUR", "mdi:arrow-collapse-down", SensorDeviceClass.MONETARY, SensorStateClass.MEASUREMENT),
    ("sensor.funda_bovengrens", "bovengrens", "bovengrens", "Bovengrens", "EUR", "mdi:arrow-collapse-up", SensorDeviceClass.MONETARY, SensorStateClass.MEASUREMENT),
    ("sensor.funda_maandwijziging", "maandwijziging", "maandwijziging", "Maandwijziging", "EUR", "mdi:trending-up", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_maandwijziging_pct", "maandwijziging_pct", "maandwijziging_2", "Maandwijziging %", "%", "mdi:percent", None, None),
    ("sensor.funda_jaarwijziging", "jaarwijziging", "jaarwijziging", "Jaarwijziging", "EUR", "mdi:chart-line", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_jaarwijziging_pct", "jaarwijziging_pct", "jaarwijziging_2", "Jaarwijziging %", "%", "mdi:percent", None, None),
    ("sensor.funda_all_time_high", "all_time_high", "all_time_high", "All-Time High", "EUR", "mdi:arrow-up-bold", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_all_time_low", "all_time_low", "all_time_low", "All-Time Low", "EUR", "mdi:arrow-down-bold", SensorDeviceClass.MONETARY, None),
    ("sensor.funda_betrouwbaarheid", "betrouwbaarheid", "betrouwbaarheid", "Betrouwbaarheid", None, "mdi:shield-check", None, None),
    ("sensor.funda_prijs_per_m2", "prijs_per_m2", "prijs_per_m2", "Prijs per m²", "EUR/m²", "mdi:ruler-square", None, None),
    ("sensor.funda_delta_status", "delta_status", "delta_status", "Delta Status", None, "mdi:arrow-up-down", None, None),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Funda Tracker sensors from a config entry."""
    runtime = hass.data[DOMAIN][entry.entry_id]
    coordinator = runtime["coordinator"]
    store = runtime["finance"]

    entities = [
        FundaSensor(coordinator, entry, store, sensor_def)
        for sensor_def in SENSOR_TYPES
    ]
    entities += [
        FundaFinanceSensor(coordinator, entry, store, finance_def)
        for finance_def in FINANCE_SENSORS
    ]
    async_add_entities(entities)


class FundaSensor(CoordinatorEntity, RestoreEntity, SensorEntity):
    """A Funda Tracker sensor that persists state across HA restarts."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, store, sensor_def):
        """Initialise the sensor."""
        super().__init__(coordinator)
        json_key, uid_suffix, object_id, name, unit, icon, device_class, state_class = sensor_def
        self._json_key = json_key
        self._store = store
        self.entity_id = ENTITY_ID_FORMAT.format(f"funda_tracker_{object_id}")
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
        self._last_known_state = None
        self._last_known_attrs = {}

    async def async_added_to_hass(self) -> None:
        """Restore last known state when HA starts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state and last_state.state not in ("unknown", "unavailable"):
            self._last_known_state = last_state.state
            self._last_known_attrs = self._clean_attributes(last_state.attributes)
        self._cache_coordinator_state()
        self._publish_house_value()

    @property
    def available(self) -> bool:
        """Keep the entity available while a last known value exists."""
        return self._last_known_state is not None

    @property
    def native_value(self):
        """Return the sensor value from coordinator data, or restored state."""
        return self._last_known_state

    @property
    def extra_state_attributes(self) -> dict:
        """Return extra attributes from coordinator data, or restored attributes."""
        attrs = dict(self._last_known_attrs)
        if self._json_key == "sensor.funda_house_value":
            updated_at = self.coordinator.last_successful_update
            if updated_at is None:
                updated_at = self._parse_timestamp(
                    attrs.get("last_successful_update") or attrs.get("last_scraped")
                )

            attrs["last_successful_update"] = (
                updated_at.isoformat() if updated_at is not None else None
            )
            attrs["update_overdue"] = self._is_update_overdue(updated_at)
        return attrs

    @staticmethod
    def _clean_attributes(source: dict) -> dict:
        """Remove attributes managed by Home Assistant itself."""
        attrs = dict(source)
        for key in ("unit_of_measurement", "friendly_name", "icon", "state_class",
                     "device_class", "restored"):
            attrs.pop(key, None)
        return attrs

    @staticmethod
    def _parse_timestamp(value) -> datetime | None:
        try:
            return datetime.fromisoformat(value) if value else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _is_update_overdue(updated_at: datetime | None) -> bool:
        if updated_at is None:
            return True
        return datetime.now(updated_at.tzinfo) - updated_at > STALE_DATA_AFTER

    def _cache_coordinator_state(self) -> None:
        """Cache fresh coordinator data without clearing the last valid value."""
        data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        sensors = data.get("sensors", {})
        sensor = sensors.get(self._json_key) if isinstance(sensors, dict) else None
        if not isinstance(sensor, dict) or sensor.get("state") is None:
            return
        self._last_known_state = sensor["state"]
        self._last_known_attrs = self._clean_attributes(sensor.get("attributes", {}))

    def _publish_house_value(self) -> None:
        """Share the house value so the finance sensors can use it too."""
        if self._json_key != HOUSE_VALUE_KEY:
            return
        try:
            self._store.set(HOUSE_VALUE_KEY, float(self._last_known_state))
        except (TypeError, ValueError):
            pass

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._cache_coordinator_state()
        self._publish_house_value()
        self.async_write_ha_state()


class FundaFinanceSensor(CoordinatorEntity, SensorEntity):
    """A value derived from the house value and one of the finance inputs."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, store, finance_def):
        """Initialise the finance sensor."""
        super().__init__(coordinator)
        uid_suffix, name, unit, icon, required_input = finance_def
        self._store = store
        self._required_input = required_input
        self.entity_id = ENTITY_ID_FORMAT.format(f"funda_tracker_{uid_suffix}")
        self._attr_unique_id = f"funda_tracker_{uid_suffix}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        if unit == "EUR":
            # No monetary device class: it only allows state_class total, which
            # would misrepresent these as cumulative figures.
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Funda Tracker",
            manufacturer="Funda",
            model="Waardecheck",
            entry_type=DeviceEntryType.SERVICE,
        )

    async def async_added_to_hass(self) -> None:
        """Recalculate whenever one of the finance inputs changes."""
        await super().async_added_to_hass()
        self._store.add_listener(self._handle_finance_update)

    async def async_will_remove_from_hass(self) -> None:
        """Stop listening for finance input changes."""
        self._store.remove_listener(self._handle_finance_update)
        await super().async_will_remove_from_hass()

    @property
    def _house_value(self) -> float | None:
        value = self._store.get(HOUSE_VALUE_KEY)
        return value if value > 0 else None

    @property
    def available(self) -> bool:
        """Stay unavailable until there is a house value and a non-zero input."""
        return self._house_value is not None and self._store.get(self._required_input) > 0

    @property
    def extra_state_attributes(self) -> dict:
        """Expose how fresh the underlying house value is."""
        updated_at = self.coordinator.last_successful_update
        return {
            "last_successful_update": updated_at.isoformat() if updated_at else None,
            "update_overdue": self.coordinator.update_overdue,
        }

    @property
    def native_value(self):
        """Return the calculated value."""
        value = self._house_value
        if value is None:
            return None

        reference = self._store.get(self._required_input)
        if reference <= 0:
            return None

        difference = value - reference
        if self._attr_native_unit_of_measurement == "%":
            return round(difference / reference * 100, 1)
        return round(difference)

    @callback
    def _handle_finance_update(self) -> None:
        """Write a new state after a finance input changed."""
        if self.hass is not None:
            self.async_write_ha_state()
