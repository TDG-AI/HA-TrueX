"""Support for TrueX covers (curtains, garage doors)."""

from __future__ import annotations

from typing import Any

from .truex_sharing import CustomerDevice, Manager

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TrueXConfigEntry
from .const import DPCode, DeviceCategory, LOGGER
from .entity import TrueXEntity

# Categories and their cover device classes
COVER_CATEGORIES: dict[str, CoverDeviceClass] = {
    DeviceCategory.CL: CoverDeviceClass.CURTAIN,
    DeviceCategory.CLKG: CoverDeviceClass.CURTAIN,
    DeviceCategory.CKMKZQ: CoverDeviceClass.GARAGE,
    DeviceCategory.MC: CoverDeviceClass.DOOR,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX covers."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXCoverEntity] = []

    for device in manager.device_map.values():
        if device.category not in COVER_CATEGORIES:
            continue
        # Must have at least a control dpcode
        if (
            DPCode.CONTROL not in device.status
            and DPCode.CONTROL not in device.functions
        ):
            continue
        entities.append(
            TrueXCoverEntity(
                coordinator,
                device,
                manager,
                COVER_CATEGORIES[device.category],
            )
        )

    LOGGER.debug("Setting up %d cover entities", len(entities))
    async_add_entities(entities)


class TrueXCoverEntity(TrueXEntity, CoverEntity):
    """TrueX Cover Entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
        device_class: CoverDeviceClass,
    ) -> None:
        """Init TrueX cover."""
        super().__init__(coordinator, device, device_manager)
        self._attr_device_class = device_class

        # Determine features
        features = (
            CoverEntityFeature.OPEN
            | CoverEntityFeature.CLOSE
            | CoverEntityFeature.STOP
        )
        if (
            DPCode.PERCENT_CONTROL in device.functions
            or DPCode.PERCENT_CONTROL in device.status
        ):
            features |= CoverEntityFeature.SET_POSITION
        self._attr_supported_features = features

    @property
    def is_closed(self) -> bool | None:
        """Return if the cover is closed."""
        # Check control state
        control = self.device_obj.status.get(DPCode.CONTROL)
        if control == "close":
            return True
        if control == "open":
            return False

        # Check position
        position = self._get_position()
        if position is not None:
            return position == 0
        return None

    @property
    def current_cover_position(self) -> int | None:
        """Return current cover position (0-100)."""
        return self._get_position()

    def _get_position(self) -> int | None:
        """Get position from available DPCodes."""
        for dpcode in (DPCode.PERCENT_STATE, DPCode.POSITION, DPCode.PERCENT_CONTROL):
            value = self.device_obj.status.get(dpcode)
            if value is not None:
                try:
                    return int(value)
                except (ValueError, TypeError):
                    continue
        return None

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._send_commands([{"code": DPCode.CONTROL, "value": "open"}])

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._send_commands([{"code": DPCode.CONTROL, "value": "close"}])

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover."""
        await self._send_commands([{"code": DPCode.CONTROL, "value": "stop"}])

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        """Set cover position."""
        position = kwargs.get(ATTR_POSITION)
        if position is not None:
            await self._send_commands(
                [{"code": DPCode.PERCENT_CONTROL, "value": int(position)}]
            )
