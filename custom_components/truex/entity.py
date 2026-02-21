"""TrueX Home Assistant Base Entity Model."""

from __future__ import annotations

from typing import Any

from truex_sharing import CustomerDevice, Manager

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, LOGGER


class TrueXEntity(CoordinatorEntity):
    """TrueX base device entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
    ) -> None:
        """Init TrueXEntity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"truex.{device.id}"
        self.device_obj = device
        self.device_manager = device_manager

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_obj.id)},
            manufacturer="TrueDigital",
            name=self.device_obj.name,
            model=self.device_obj.product_name or self.device_obj.category,
            model_id=self.device_obj.product_id,
        )

    @property
    def available(self) -> bool:
        """Return if the device is available."""
        return self.device_obj.online

    async def _send_commands(self, commands: list[dict[str, Any]]) -> None:
        """Send a list of commands to the device."""
        LOGGER.debug("Sending commands for device %s: %s", self.device_obj.id, commands)
        if not commands:
            return
        await self.device_manager.send_commands(self.device_obj.id, commands)
        # Request a coordinator refresh to update the state
        await self.coordinator.async_request_refresh()
