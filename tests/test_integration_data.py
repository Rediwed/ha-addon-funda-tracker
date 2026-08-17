import importlib
import json
import sys
import tempfile
import types
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch


def import_integration_module():
    homeassistant = types.ModuleType("homeassistant")
    config_entries = types.ModuleType("homeassistant.config_entries")
    config_entries.ConfigEntry = type("ConfigEntry", (), {})
    core = types.ModuleType("homeassistant.core")
    core.HomeAssistant = type("HomeAssistant", (), {})
    helpers = types.ModuleType("homeassistant.helpers")
    update_coordinator = types.ModuleType(
        "homeassistant.helpers.update_coordinator"
    )
    update_coordinator.DataUpdateCoordinator = type(
        "DataUpdateCoordinator", (), {}
    )

    modules = {
        "homeassistant": homeassistant,
        "homeassistant.config_entries": config_entries,
        "homeassistant.core": core,
        "homeassistant.helpers": helpers,
        "homeassistant.helpers.update_coordinator": update_coordinator,
    }
    with patch.dict(sys.modules, modules):
        return importlib.import_module("custom_components.funda_tracker")


integration = import_integration_module()


class CoordinatorDataTests(unittest.TestCase):
    def create_coordinator(self, data_path):
        coordinator = object.__new__(integration.FundaDataCoordinator)
        coordinator._path = data_path
        coordinator._data_issue = None
        coordinator.last_successful_update = None
        coordinator.update_overdue = True
        return coordinator

    def test_missing_or_invalid_file_keeps_last_valid_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_path = Path(temporary_directory) / "sensors.json"
            payload = {
                "last_updated": datetime.now().isoformat(),
                "sensors": {
                    "sensor.funda_house_value": {
                        "state": 500_000,
                        "attributes": {},
                    }
                },
            }
            data_path.write_text(json.dumps(payload))
            coordinator = self.create_coordinator(data_path)

            valid_data = coordinator._read_data({})
            data_path.unlink()
            self.assertIs(coordinator._read_data(valid_data), valid_data)

            data_path.write_text("not json")
            self.assertIs(coordinator._read_data(valid_data), valid_data)
            self.assertEqual(
                valid_data["sensors"]["sensor.funda_house_value"]["state"],
                500_000,
            )

    def test_old_payload_is_available_but_marked_overdue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_path = Path(temporary_directory) / "sensors.json"
            payload = {
                "last_updated": (datetime.now() - timedelta(days=36)).isoformat(),
                "sensors": {
                    "sensor.funda_house_value": {
                        "state": 500_000,
                        "attributes": {},
                    }
                },
            }
            data_path.write_text(json.dumps(payload))
            coordinator = self.create_coordinator(data_path)

            self.assertEqual(coordinator._read_data({}), payload)
            self.assertTrue(coordinator.update_overdue)


if __name__ == "__main__":
    unittest.main()