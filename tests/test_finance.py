import importlib
import sys
import types
import unittest
from unittest.mock import patch


def stub_home_assistant():
    """Provide just enough of Home Assistant to import the integration modules."""
    homeassistant = types.ModuleType("homeassistant")

    components = types.ModuleType("homeassistant.components")
    sensor_module = types.ModuleType("homeassistant.components.sensor")
    sensor_module.SensorEntity = type("SensorEntity", (), {})
    sensor_module.SensorDeviceClass = type(
        "SensorDeviceClass", (), {"MONETARY": "monetary"}
    )
    sensor_module.SensorStateClass = type(
        "SensorStateClass", (), {"MEASUREMENT": "measurement"}
    )

    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})

    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    core.callback = lambda func: func

    helpers = types.ModuleType("homeassistant.helpers")
    device_registry = types.ModuleType("homeassistant.helpers.device_registry")
    device_registry.DeviceEntryType = type("DeviceEntryType", (), {"SERVICE": "service"})
    entity = types.ModuleType("homeassistant.helpers.entity")
    entity.DeviceInfo = dict
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_platform.AddEntitiesCallback = object
    restore_state = types.ModuleType("homeassistant.helpers.restore_state")
    restore_state.RestoreEntity = type("RestoreEntity", (), {})
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    update_coordinator.CoordinatorEntity = type("CoordinatorEntity", (), {})
    update_coordinator.DataUpdateCoordinator = type("DataUpdateCoordinator", (), {})

    return {
        "homeassistant": homeassistant,
        "homeassistant.components": components,
        "homeassistant.components.sensor": sensor_module,
        "homeassistant.config_entries": config_entries,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.device_registry": device_registry,
        "homeassistant.helpers.entity": entity,
        "homeassistant.helpers.entity_platform": entity_platform,
        "homeassistant.helpers.restore_state": restore_state,
        "homeassistant.helpers.update_coordinator": update_coordinator,
    }


with patch.dict(sys.modules, stub_home_assistant()):
    integration = importlib.import_module("custom_components.funda_tracker")
    sensor = importlib.import_module("custom_components.funda_tracker.sensor")
    const = importlib.import_module("custom_components.funda_tracker.const")


class FinanceStoreTests(unittest.TestCase):
    def test_unset_amount_defaults_to_zero(self):
        store = integration.FinanceStore()

        self.assertEqual(store.get("purchase_price"), 0.0)

    def test_listeners_are_notified_on_change(self):
        store = integration.FinanceStore()
        calls = []
        store.add_listener(lambda: calls.append(True))

        store.set("purchase_price", 300_000)

        self.assertEqual(len(calls), 1)
        self.assertEqual(store.get("purchase_price"), 300_000)

    def test_removed_listener_is_not_notified(self):
        store = integration.FinanceStore()
        calls = []

        def listener():
            calls.append(True)

        store.add_listener(listener)
        store.remove_listener(listener)
        store.set("mortgage_balance", 100_000)

        self.assertEqual(calls, [])


class FinanceSensorTests(unittest.TestCase):
    def build_sensor(self, uid_suffix, house_value, amounts):
        definition = next(f for f in const.FINANCE_SENSORS if f[0] == uid_suffix)
        store = integration.FinanceStore()
        if house_value is not None:
            store.set(sensor.HOUSE_VALUE_KEY, house_value)
        for key, value in amounts.items():
            store.set(key, value)

        entity = object.__new__(sensor.FundaFinanceSensor)
        entity._store = store
        entity._required_input = definition[4]
        entity._attr_native_unit_of_measurement = definition[2]
        entity.coordinator = types.SimpleNamespace(
            data={},
            last_successful_update=None,
            update_overdue=False,
        )
        return entity

    def test_equity_subtracts_mortgage(self):
        entity = self.build_sensor("overwaarde", 400_000, {"mortgage_balance": 100_000})

        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, 300_000)

    def test_market_gain_can_be_negative(self):
        entity = self.build_sensor("marktwinst", 250_000, {"purchase_price": 300_000})

        self.assertEqual(entity.native_value, -50_000)

    def test_roi_is_a_percentage(self):
        entity = self.build_sensor("markt_roi", 400_000, {"purchase_price": 200_000})

        self.assertAlmostEqual(entity.native_value, 100.0, places=1)

    def test_total_profit_uses_total_investment(self):
        entity = self.build_sensor("totale_winst", 400_000, {"total_investment": 250_000})

        self.assertEqual(entity.native_value, 150_000)

    def test_total_roi_uses_total_investment(self):
        entity = self.build_sensor("totale_roi", 200_000, {"total_investment": 400_000})

        self.assertAlmostEqual(entity.native_value, -50.0, places=1)

    def test_unavailable_until_the_amount_is_set(self):
        entity = self.build_sensor("overwaarde", 400_000, {})

        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)

    def test_unavailable_without_a_house_value(self):
        entity = self.build_sensor("overwaarde", None, {"mortgage_balance": 100_000})

        self.assertFalse(entity.available)
        self.assertIsNone(entity.native_value)

    def test_restored_house_value_keeps_finance_sensors_working(self):
        entity = self.build_sensor("overwaarde", 400_000, {"mortgage_balance": 100_000})
        entity.coordinator.data = {}

        self.assertTrue(entity.available)
        self.assertEqual(entity.native_value, 300_000)

    def test_staleness_is_exposed_as_attributes(self):
        entity = self.build_sensor("overwaarde", 400_000, {"mortgage_balance": 100_000})
        entity.coordinator.update_overdue = True

        self.assertTrue(entity.extra_state_attributes["update_overdue"])
        self.assertIsNone(entity.extra_state_attributes["last_successful_update"])


if __name__ == "__main__":
    unittest.main()
