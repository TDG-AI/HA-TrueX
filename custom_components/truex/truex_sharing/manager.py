"""TrueX device manager.

Equivalent to tuya_sharing.manager.Manager.
"""

from __future__ import annotations

import json
from typing import Any

from .customerapi import CustomerApi
from .customerlogging import logger
from .device import CustomerDevice


class DeviceListener:
    """Listener for device update events."""

    def update_device(self, device: CustomerDevice) -> None:
        """Called when device status is updated."""

    def add_device(self, device: CustomerDevice) -> None:
        """Called when a new device is discovered."""

    def remove_device(self, device_id: str) -> None:
        """Called when a device is removed."""


class Manager:
    """Manages TrueX devices via the OPENAPI CUBE.

    Equivalent to tuya_sharing.manager.Manager.
    """

    def __init__(self, api: CustomerApi, uid: str) -> None:
        """Initialize the device manager."""
        self.api = api
        self.uid = uid
        self.device_map: dict[str, CustomerDevice] = {}
        self.device_listeners: list[DeviceListener] = []

    def add_device_listener(self, listener: DeviceListener) -> None:
        """Register a device listener."""
        self.device_listeners.append(listener)

    async def update_device_cache(self) -> None:
        """Fetch all devices for the user and populate the device map."""
        response = await self.api.get_user_devices(self.uid)
        if not response.get("success"):
            logger.error("Failed to get devices: %s", response)
            return

        devices_data = response.get("result", [])
        logger.debug("Found %d devices", len(devices_data))

        for dev_data in devices_data:
            device_id = dev_data.get("id", "")
            if not device_id:
                continue

            device = CustomerDevice.from_api_response(dev_data)

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

    async def _fetch_device_specifications(self, device: CustomerDevice) -> None:
        """Fetch and store device specifications (functions and status range)."""
        try:
            response = await self.api.get_device_specifications(device.id)
            if not response.get("success"):
                logger.debug(
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
                        parsed_values = (
                            json.loads(values)
                            if isinstance(values, str)
                            else values
                        )
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
                        parsed_values = (
                            json.loads(values)
                            if isinstance(values, str)
                            else values
                        )
                    except (json.JSONDecodeError, TypeError):
                        parsed_values = {}
                    device.status_range[code] = {
                        "type": sr.get("type", ""),
                        "values": parsed_values,
                    }

        except Exception:
            logger.exception("Error fetching specifications for %s", device.id)

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
                    # Notify listeners
                    for listener in self.device_listeners:
                        listener.update_device(device)
                else:
                    logger.debug(
                        "Failed to update status for %s: %s", device_id, response
                    )
            except Exception:
                logger.exception("Error updating status for %s", device_id)

    async def send_commands(
        self, device_id: str, commands: list[dict[str, Any]]
    ) -> bool:
        """Send commands to a device."""
        try:
            response = await self.api.send_device_commands(device_id, commands)
            if response.get("success"):
                logger.debug("Commands sent to %s: %s", device_id, commands)
                return True
            logger.error(
                "Failed to send commands to %s: %s", device_id, response
            )
            return False
        except Exception:
            logger.exception("Error sending commands to %s", device_id)
            return False

    async def get_device_stream_allocate(
        self, device_id: str, stream_type: str
    ) -> str | None:
        """Get the live streaming URL for a device."""
        try:
            response = await self.api.get_device_stream_allocate(
                self.uid, device_id, stream_type.upper()
            )
            if response.get("success"):
                return response.get("result", {}).get("url")
            logger.error(
                "Failed to allocate stream for %s: %s",
                device_id,
                response,
            )
        except Exception:
            logger.exception(
                "Error allocating stream for %s", device_id
            )
        return None
