"""Support for TrueX climate devices."""

from __future__ import annotations

from typing import Any

from .truex_sharing import CustomerDevice, Manager

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TrueXConfigEntry
from .const import DPCode, DeviceCategory, LOGGER
from .entity import TrueXEntity

# Categories that produce climate entities
CLIMATE_CATEGORIES: set[str] = {
    DeviceCategory.KT,      # Air conditioner
    DeviceCategory.WK,      # Thermostat
    DeviceCategory.KTKZQ,   # AC controller
}

# Tuya mode → HVAC mode mapping
TUYA_MODE_TO_HVAC: dict[str, HVACMode] = {
    "cold": HVACMode.COOL,
    "hot": HVACMode.HEAT,
    "wind": HVACMode.FAN_ONLY,
    "auto": HVACMode.AUTO,
    "wet": HVACMode.DRY,
}

HVAC_TO_TUYA_MODE: dict[HVACMode, str] = {v: k for k, v in TUYA_MODE_TO_HVAC.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX climate entities."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXClimateEntity] = []

    for device in manager.device_map.values():
        if device.category not in CLIMATE_CATEGORIES:
            continue
        # Must have at least a switch dpcode
        if DPCode.SWITCH not in device.status and DPCode.SWITCH not in device.functions:
            continue
        entities.append(TrueXClimateEntity(coordinator, device, manager))

    LOGGER.debug("Setting up %d climate entities", len(entities))
    async_add_entities(entities)


class TrueXClimateEntity(TrueXEntity, ClimateEntity):
    """TrueX Climate Entity."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
    ) -> None:
        """Init TrueX climate."""
        super().__init__(coordinator, device, device_manager)

        # Determine features
        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        if DPCode.TEMP_SET in device.functions or DPCode.TEMP_SET in device.status:
            features |= ClimateEntityFeature.TARGET_TEMPERATURE
        if (
            DPCode.FAN_SPEED_ENUM in device.functions
            or DPCode.FAN_SPEED_ENUM in device.status
        ):
            features |= ClimateEntityFeature.FAN_MODE
        self._attr_supported_features = features

        # HVAC modes
        modes = [HVACMode.OFF]
        if DPCode.MODE in device.functions:
            mode_values = device.functions[DPCode.MODE].get("values", {})
            mode_range = mode_values.get("range", [])
            for tuya_mode in mode_range:
                if tuya_mode in TUYA_MODE_TO_HVAC:
                    modes.append(TUYA_MODE_TO_HVAC[tuya_mode])
        if len(modes) == 1:
            # No specific modes, add defaults
            modes.extend([HVACMode.COOL, HVACMode.HEAT, HVACMode.AUTO])
        self._attr_hvac_modes = modes

        # Fan modes
        if DPCode.FAN_SPEED_ENUM in device.functions:
            fan_values = device.functions[DPCode.FAN_SPEED_ENUM].get("values", {})
            self._attr_fan_modes = fan_values.get("range", ["low", "mid", "high"])
        elif DPCode.FAN_SPEED_ENUM in device.status_range:
            fan_values = device.status_range[DPCode.FAN_SPEED_ENUM].get("values", {})
            self._attr_fan_modes = fan_values.get("range", ["low", "mid", "high"])

        # Temperature range
        if DPCode.TEMP_SET in device.functions:
            temp_values = device.functions[DPCode.TEMP_SET].get("values", {})
            self._attr_min_temp = temp_values.get("min", 16)
            self._attr_max_temp = temp_values.get("max", 30)
            self._attr_target_temperature_step = temp_values.get("step", 1)

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode."""
        switch_on = self.device_obj.status.get(DPCode.SWITCH)
        if not switch_on:
            return HVACMode.OFF

        mode = self.device_obj.status.get(DPCode.MODE, "")
        return TUYA_MODE_TO_HVAC.get(mode, HVACMode.AUTO)

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        value = self.device_obj.status.get(DPCode.TEMP_CURRENT)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        value = self.device_obj.status.get(DPCode.TEMP_SET)
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        return self.device_obj.status.get(DPCode.FAN_SPEED_ENUM)

    @property
    def current_humidity(self) -> int | None:
        """Return current humidity."""
        value = self.device_obj.status.get(DPCode.HUMIDITY_CURRENT)
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode == HVACMode.OFF:
            await self._send_commands([{"code": DPCode.SWITCH, "value": False}])
            return

        commands: list[dict[str, Any]] = [
            {"code": DPCode.SWITCH, "value": True},
        ]
        tuya_mode = HVAC_TO_TUYA_MODE.get(hvac_mode)
        if tuya_mode:
            commands.append({"code": DPCode.MODE, "value": tuya_mode})
        await self._send_commands(commands)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        await self._send_commands(
            [{"code": DPCode.TEMP_SET, "value": int(temperature)}]
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set fan mode."""
        await self._send_commands(
            [{"code": DPCode.FAN_SPEED_ENUM, "value": fan_mode}]
        )

    async def async_turn_on(self) -> None:
        """Turn on."""
        await self._send_commands([{"code": DPCode.SWITCH, "value": True}])

    async def async_turn_off(self) -> None:
        """Turn off."""
        await self._send_commands([{"code": DPCode.SWITCH, "value": False}])
