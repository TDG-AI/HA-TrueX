"""Support for TrueX sensors."""

from __future__ import annotations

from dataclasses import dataclass

from truex_sharing import CustomerDevice, Manager

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TrueXConfigEntry
from .const import DPCode, DeviceCategory, LOGGER
from .entity import TrueXEntity


@dataclass(frozen=True)
class TrueXSensorDescription(SensorEntityDescription):
    """Describe a TrueX sensor."""

    dpcode: str = ""
    scale: float = 1.0  # Division factor for raw value


# Sensor definitions mapped by device category
SENSORS: dict[str, list[TrueXSensorDescription]] = {
    # Temperature and humidity sensor
    DeviceCategory.WSDCG: [
        TrueXSensorDescription(
            key="temperature",
            dpcode=DPCode.VA_TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            scale=10.0,
        ),
        TrueXSensorDescription(
            key="humidity",
            dpcode=DPCode.VA_HUMIDITY,
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
            scale=10.0,
        ),
    ],
    # Smart electricity meter
    DeviceCategory.ZNDB: [
        TrueXSensorDescription(
            key="power",
            dpcode=DPCode.CUR_POWER,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfPower.WATT,
            scale=10.0,
        ),
        TrueXSensorDescription(
            key="voltage",
            dpcode=DPCode.CUR_VOLTAGE,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricPotential.VOLT,
            scale=10.0,
        ),
        TrueXSensorDescription(
            key="current",
            dpcode=DPCode.CUR_CURRENT,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfElectricCurrent.MILLIAMPERE,
        ),
        TrueXSensorDescription(
            key="energy",
            dpcode=DPCode.ADD_ELE,
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
            scale=100.0,
        ),
    ],
    # CO2 detector
    DeviceCategory.CO2BJ: [
        TrueXSensorDescription(
            key="co2",
            dpcode=DPCode.CO2_VALUE,
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="ppm",
        ),
    ],
    # Air quality monitor
    DeviceCategory.HJJCY: [
        TrueXSensorDescription(
            key="pm25",
            dpcode=DPCode.PM25_VALUE,
            device_class=SensorDeviceClass.PM25,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="µg/m³",
        ),
        TrueXSensorDescription(
            key="co2",
            dpcode=DPCode.CO2_VALUE,
            device_class=SensorDeviceClass.CO2,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="ppm",
        ),
        TrueXSensorDescription(
            key="voc",
            dpcode=DPCode.VOC_VALUE,
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="µg/m³",
        ),
        TrueXSensorDescription(
            key="ch2o",
            dpcode=DPCode.CH2O_VALUE,
            device_class=SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="mg/m³",
            scale=100.0,
        ),
        TrueXSensorDescription(
            key="temperature",
            dpcode=DPCode.VA_TEMPERATURE,
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=UnitOfTemperature.CELSIUS,
            scale=10.0,
        ),
        TrueXSensorDescription(
            key="humidity",
            dpcode=DPCode.VA_HUMIDITY,
            device_class=SensorDeviceClass.HUMIDITY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement=PERCENTAGE,
        ),
    ],
}

# Generic sensors that apply to ANY device category if the dpcode exists
GENERIC_SENSORS: list[TrueXSensorDescription] = [
    TrueXSensorDescription(
        key="battery",
        dpcode=DPCode.BATTERY_PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX sensors."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXSensorEntity] = []

    for device in manager.device_map.values():
        # Category-specific sensors
        if device.category in SENSORS:
            for description in SENSORS[device.category]:
                if (
                    description.dpcode in device.status
                    or description.dpcode in device.status_range
                ):
                    entities.append(
                        TrueXSensorEntity(coordinator, device, manager, description)
                    )

        # Generic sensors (e.g., battery) for any device
        for description in GENERIC_SENSORS:
            if (
                description.dpcode in device.status
                or description.dpcode in device.status_range
            ):
                entities.append(
                    TrueXSensorEntity(coordinator, device, manager, description)
                )

    LOGGER.debug("Setting up %d sensor entities", len(entities))
    async_add_entities(entities)


class TrueXSensorEntity(TrueXEntity, SensorEntity):
    """TrueX Sensor Entity."""

    entity_description: TrueXSensorDescription

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
        description: TrueXSensorDescription,
    ) -> None:
        """Init TrueX sensor."""
        super().__init__(coordinator, device, device_manager)
        self.entity_description = description
        self._attr_unique_id = f"truex.{device.id}.{description.key}"

    @property
    def native_value(self) -> float | int | str | None:
        """Return the sensor value."""
        value = self.device_obj.status.get(self.entity_description.dpcode)
        if value is None:
            return None
        try:
            numeric = float(value)
            if self.entity_description.scale != 1.0:
                return round(numeric / self.entity_description.scale, 1)
            return numeric
        except (ValueError, TypeError):
            return value
