"""Support for TrueX binary sensors."""

from __future__ import annotations

from dataclasses import dataclass

from truex_sharing import CustomerDevice, Manager

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TrueXConfigEntry
from .const import DPCode, DeviceCategory, LOGGER
from .entity import TrueXEntity


@dataclass(frozen=True)
class TrueXBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a TrueX binary sensor."""

    dpcode: str = ""
    on_value: str | bool = True  # Value that means "on" / "detected"


# Binary sensor definitions by category
BINARY_SENSORS: dict[str, list[TrueXBinarySensorDescription]] = {
    # Contact sensor (door/window)
    DeviceCategory.MCS: [
        TrueXBinarySensorDescription(
            key="contact",
            dpcode=DPCode.DOORCONTACT_STATE,
            device_class=BinarySensorDeviceClass.DOOR,
            on_value=True,
        ),
    ],
    # Motion sensor
    DeviceCategory.PIR_CAT: [
        TrueXBinarySensorDescription(
            key="motion",
            dpcode=DPCode.PIR,
            device_class=BinarySensorDeviceClass.MOTION,
            on_value="pir",
        ),
    ],
    # Water leak detector
    DeviceCategory.SJ: [
        TrueXBinarySensorDescription(
            key="water_leak",
            dpcode=DPCode.WATERSENSOR_STATE,
            device_class=BinarySensorDeviceClass.MOISTURE,
            on_value="alarm",
        ),
    ],
    # Smoke alarm
    DeviceCategory.YWBJ: [
        TrueXBinarySensorDescription(
            key="smoke",
            dpcode=DPCode.SMOKE_SENSOR_STATUS,
            device_class=BinarySensorDeviceClass.SMOKE,
            on_value="alarm",
        ),
        TrueXBinarySensorDescription(
            key="smoke_state",
            dpcode=DPCode.SMOKE_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.SMOKE,
            on_value="1",
        ),
    ],
    # Gas alarm
    DeviceCategory.RQBJ: [
        TrueXBinarySensorDescription(
            key="gas",
            dpcode=DPCode.GAS_SENSOR_STATUS,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="alarm",
        ),
        TrueXBinarySensorDescription(
            key="gas_state",
            dpcode=DPCode.GAS_SENSOR_STATE,
            device_class=BinarySensorDeviceClass.GAS,
            on_value="1",
        ),
    ],
    # CO detector
    DeviceCategory.COBJ: [
        TrueXBinarySensorDescription(
            key="co",
            dpcode=DPCode.CO_STATUS,
            device_class=BinarySensorDeviceClass.CO,
            on_value="alarm",
        ),
        TrueXBinarySensorDescription(
            key="co_state",
            dpcode=DPCode.CO_STATE,
            device_class=BinarySensorDeviceClass.CO,
            on_value="1",
        ),
    ],
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX binary sensors."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXBinarySensorEntity] = []

    for device in manager.device_map.values():
        if device.category not in BINARY_SENSORS:
            continue
        for description in BINARY_SENSORS[device.category]:
            if (
                description.dpcode in device.status
                or description.dpcode in device.status_range
            ):
                entities.append(
                    TrueXBinarySensorEntity(coordinator, device, manager, description)
                )

    LOGGER.debug("Setting up %d binary sensor entities", len(entities))
    async_add_entities(entities)


class TrueXBinarySensorEntity(TrueXEntity, BinarySensorEntity):
    """TrueX Binary Sensor Entity."""

    entity_description: TrueXBinarySensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
        description: TrueXBinarySensorDescription,
    ) -> None:
        """Init TrueX binary sensor."""
        super().__init__(coordinator, device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"truex.{device.id}.{description.key}"

    @property
    def is_on(self) -> bool | None:
        """Return true if sensor is on / triggered."""
        value = self.device_obj.status.get(self.entity_description.dpcode)
        if value is None:
            return None
        return value == self.entity_description.on_value
