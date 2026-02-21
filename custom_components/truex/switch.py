"""Support for TrueX switches."""

from __future__ import annotations

from typing import Any

from .truex_sharing import CustomerDevice, Manager

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TrueXConfigEntry
from .const import DPCode, DeviceCategory, LOGGER
from .entity import TrueXEntity

# Categories that should produce switch entities
SWITCH_CATEGORIES: set[str] = {
    DeviceCategory.KG,      # Switch
    DeviceCategory.CZ,      # Socket
    DeviceCategory.PC,      # Power strip
    DeviceCategory.DLQ,     # Circuit breaker
}

# DPCodes to look for, in priority order
SWITCH_DPCODES: list[str] = [
    DPCode.SWITCH_1,
    DPCode.SWITCH_2,
    DPCode.SWITCH_3,
    DPCode.SWITCH_4,
    DPCode.SWITCH_5,
    DPCode.SWITCH_6,
    DPCode.SWITCH_7,
    DPCode.SWITCH_8,
    DPCode.SWITCH,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX switches."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXSwitchEntity] = []

    for device in manager.device_map.values():
        if device.category not in SWITCH_CATEGORIES:
            continue

        # Find which switch DPCodes this device supports
        for dpcode in SWITCH_DPCODES:
            if dpcode in device.status or dpcode in device.functions:
                entities.append(
                    TrueXSwitchEntity(coordinator, device, manager, dpcode)
                )

    LOGGER.debug("Setting up %d switch entities", len(entities))
    async_add_entities(entities)


class TrueXSwitchEntity(TrueXEntity, SwitchEntity):
    """TrueX Switch Entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
        dpcode: str,
    ) -> None:
        """Init TrueX switch."""
        super().__init__(coordinator, device, device_manager)
        self._dpcode = dpcode
        # Make unique ID include the dpcode for multi-switch devices
        self._attr_unique_id = f"truex.{device.id}.{dpcode}"
        # Name suffix for multi-switch (e.g., "Switch 1", "Switch 2")
        if dpcode != DPCode.SWITCH:
            suffix = dpcode.replace("switch_", "")
            self._attr_translation_key = f"switch_{suffix}"
            self._attr_name = f"Switch {suffix}"

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        value = self.device_obj.status.get(self._dpcode)
        if value is None:
            return None
        return bool(value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._send_commands([{"code": self._dpcode, "value": True}])

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._send_commands([{"code": self._dpcode, "value": False}])
