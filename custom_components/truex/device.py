"""TrueX device data models and manager."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from .truex_api import TrueXAPI

_LOGGER = logging.getLogger(__name__)


@dataclass
class TrueXDevice:
    """Representation of a TrueX/Tuya device."""

    id: str
    name: str
    category: str
    product_id: str
    product_name: str
    online: bool = False
    icon: str = ""
    ip: str = ""
    time_zone: str = ""
    local_key: str = ""
    sub: bool = False
    uuid: str = ""
    active_time: int = 0
    create_time: int = 0
    update_time: int = 0

    # Runtime data populated after fetching
    status: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, dict[str, Any]] = field(default_factory=dict)
    status_range: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Flag to indicate entity setup is complete (for subscription purposes)
    set_up: bool = False

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> TrueXDevice:
        """Create a TrueXDevice from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            category=data.get("category", ""),
            product_id=data.get("product_id", ""),
            product_name=data.get("product_name", ""),
            online=data.get("online", False),
            icon=data.get("icon", ""),
            ip=data.get("ip", ""),
            time_zone=data.get("time_zone", ""),
            local_key=data.get("local_key", ""),
            sub=data.get("sub", False),
            uuid=data.get("uuid", ""),
            active_time=data.get("active_time", 0),
            create_time=data.get("create_time", 0),
            update_time=data.get("update_time", 0),
        )


class TrueXDeviceManager:
    """Manages TrueX devices via the OPENAPI CUBE."""

    def __init__(self, api: TrueXAPI, uid: str) -> None:
        """Initialize the device manager."""
        self.api = api
        self.uid = uid
        self.device_map: dict[str, TrueXDevice] = {}

    async def update_device_cache(self) -> None:
        """Fetch all devices for the user and populate the device map."""
        response = await self.api.get_user_devices(self.uid)
        if not response.get("success"):
            _LOGGER.error("Failed to get devices: %s", response)
            return

        devices_data = response.get("result", [])
        _LOGGER.debug("Found %d devices", len(devices_data))

        for dev_data in devices_data:
            device_id = dev_data.get("id", "")
            if not device_id:
                continue

            device = TrueXDevice.from_api_response(dev_data)

            # Parse status from the device list response
            status_list = dev_data.get("status", [])
            for status_item in status_list:
                code = status_item.get("code", "")
                value = status_item.get("value")
                if code:
                    device.status[code] = value

            self.device_map[device_id] = device

        # Fetch specifications for each device
        for device_id, device in self.device_map.items():
            await self._fetch_device_specifications(device)

    async def _fetch_device_specifications(self, device: TrueXDevice) -> None:
        """Fetch and store device specifications (functions and status range)."""
        try:
            response = await self.api.get_device_specifications(device.id)
            if not response.get("success"):
                _LOGGER.debug(
                    "No specifications for device %s: %s", device.id, response
                )
                return

            result = response.get("result", {})

            # Parse functions
            for func in result.get("functions", []):
                code = func.get("code", "")
                if code:
                    values = func.get("values", "{}")
                    try:
                        parsed_values = json.loads(values) if isinstance(values, str) else values
                    except (json.JSONDecodeError, TypeError):
                        parsed_values = {}
                    device.functions[code] = {
                        "type": func.get("type", ""),
                        "values": parsed_values,
                    }

            # Parse status range
            for sr in result.get("status", []):
                code = sr.get("code", "")
                if code:
                    values = sr.get("values", "{}")
                    try:
                        parsed_values = json.loads(values) if isinstance(values, str) else values
                    except (json.JSONDecodeError, TypeError):
                        parsed_values = {}
                    device.status_range[code] = {
                        "type": sr.get("type", ""),
                        "values": parsed_values,
                    }

        except Exception:
            _LOGGER.exception("Error fetching specifications for %s", device.id)

    async def update_device_status(self) -> None:
        """Poll status updates for all devices."""
        for device_id, device in self.device_map.items():
            try:
                response = await self.api.get_device_status(device_id)
                if response.get("success"):
                    status_list = response.get("result", [])
                    for status_item in status_list:
                        code = status_item.get("code", "")
                        value = status_item.get("value")
                        if code:
                            device.status[code] = value
                else:
                    _LOGGER.debug(
                        "Failed to update status for %s: %s", device_id, response
                    )
            except Exception:
                _LOGGER.exception("Error updating status for %s", device_id)

    async def send_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> bool:
        """Send commands to a device."""
        try:
            response = await self.api.send_device_commands(device_id, commands)
            if response.get("success"):
                _LOGGER.debug("Commands sent to %s: %s", device_id, commands)
                return True
            _LOGGER.error(
                "Failed to send commands to %s: %s", device_id, response
            )
            return False
        except Exception:
            _LOGGER.exception("Error sending commands to %s", device_id)
            return False
