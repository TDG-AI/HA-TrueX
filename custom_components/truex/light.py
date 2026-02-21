"""Support for TrueX lights."""

from __future__ import annotations

import json
from typing import Any

from truex_sharing import CustomerDevice, Manager

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from . import TrueXConfigEntry
from .const import DPCode, DeviceCategory, LOGGER
from .entity import TrueXEntity

# Categories that produce light entities
LIGHT_CATEGORIES: set[str] = {
    DeviceCategory.DJ,      # Light
    DeviceCategory.XDD,     # Ceiling light
    DeviceCategory.FWD,     # Ambiance light
    DeviceCategory.DC,      # String lights
    DeviceCategory.DD,      # Strip lights
    DeviceCategory.TGKG,    # Dimmer switch
    DeviceCategory.TGQ,     # Dimmer
    DeviceCategory.FSD,     # Ceiling fan light
}

# On/off DPCodes
LIGHT_SWITCH_DPCODES = [DPCode.SWITCH_LED, DPCode.SWITCH_LED_1, DPCode.SWITCH]

# Brightness DPCodes
BRIGHTNESS_DPCODES = [DPCode.BRIGHT_VALUE_V2, DPCode.BRIGHT_VALUE]

# Color temperature DPCodes
COLOR_TEMP_DPCODES = [DPCode.TEMP_VALUE_V2, DPCode.TEMP_VALUE]

# Color data DPCodes (HSV in JSON)
COLOR_DATA_DPCODES = [DPCode.COLOUR_DATA_V2, DPCode.COLOUR_DATA]

# Default brightness range
DEFAULT_BRIGHT_MIN = 10
DEFAULT_BRIGHT_MAX = 1000

# Default color temp range (in device units, maps to Kelvin)
DEFAULT_TEMP_MIN = 0
DEFAULT_TEMP_MAX = 1000

# Kelvin range for Tuya lights
MIN_KELVIN = 2700
MAX_KELVIN = 6500


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX lights."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXLightEntity] = []

    for device in manager.device_map.values():
        if device.category not in LIGHT_CATEGORIES:
            continue
        entities.append(TrueXLightEntity(coordinator, device, manager))

    LOGGER.debug("Setting up %d light entities", len(entities))
    async_add_entities(entities)


class TrueXLightEntity(TrueXEntity, LightEntity):
    """TrueX Light Entity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
    ) -> None:
        """Init TrueX light."""
        super().__init__(coordinator, device, device_manager)

        # Determine which DPCodes this light supports
        self._switch_dpcode = self._find_dpcode(LIGHT_SWITCH_DPCODES)
        self._brightness_dpcode = self._find_dpcode(BRIGHTNESS_DPCODES)
        self._color_temp_dpcode = self._find_dpcode(COLOR_TEMP_DPCODES)
        self._color_data_dpcode = self._find_dpcode(COLOR_DATA_DPCODES)
        self._work_mode_dpcode = (
            DPCode.WORK_MODE
            if DPCode.WORK_MODE in device.status or DPCode.WORK_MODE in device.functions
            else None
        )

        # Determine supported color modes
        modes: set[ColorMode] = set()
        if self._color_data_dpcode:
            modes.add(ColorMode.HS)
        if self._color_temp_dpcode:
            modes.add(ColorMode.COLOR_TEMP)
        if self._brightness_dpcode and not modes:
            modes.add(ColorMode.BRIGHTNESS)
        if not modes:
            modes.add(ColorMode.ONOFF)

        self._attr_supported_color_modes = modes

        # Kelvin range
        if ColorMode.COLOR_TEMP in modes:
            self._attr_min_color_temp_kelvin = MIN_KELVIN
            self._attr_max_color_temp_kelvin = MAX_KELVIN

        # Brightness range from specs
        self._bright_min = DEFAULT_BRIGHT_MIN
        self._bright_max = DEFAULT_BRIGHT_MAX
        if self._brightness_dpcode and self._brightness_dpcode in device.functions:
            func_values = device.functions[self._brightness_dpcode].get("values", {})
            self._bright_min = func_values.get("min", DEFAULT_BRIGHT_MIN)
            self._bright_max = func_values.get("max", DEFAULT_BRIGHT_MAX)

        # Color temp range from specs
        self._temp_min = DEFAULT_TEMP_MIN
        self._temp_max = DEFAULT_TEMP_MAX
        if self._color_temp_dpcode and self._color_temp_dpcode in device.functions:
            func_values = device.functions[self._color_temp_dpcode].get("values", {})
            self._temp_min = func_values.get("min", DEFAULT_TEMP_MIN)
            self._temp_max = func_values.get("max", DEFAULT_TEMP_MAX)

    def _find_dpcode(self, dpcodes: list[str]) -> str | None:
        """Find the first available dpcode from a list."""
        for dpcode in dpcodes:
            if dpcode in self.device_obj.status or dpcode in self.device_obj.functions:
                return dpcode
        return None

    @property
    def is_on(self) -> bool | None:
        """Return true if light is on."""
        if self._switch_dpcode:
            value = self.device_obj.status.get(self._switch_dpcode)
            if value is not None:
                return bool(value)
        return None

    @property
    def brightness(self) -> int | None:
        """Return the brightness 0-255."""
        if not self._brightness_dpcode:
            return None
        value = self.device_obj.status.get(self._brightness_dpcode)
        if value is None:
            return None
        # Scale from device range to 0-255
        return self._scale(int(value), self._bright_min, self._bright_max, 0, 255)

    @property
    def color_temp_kelvin(self) -> int | None:
        """Return the color temperature in Kelvin."""
        if not self._color_temp_dpcode:
            return None
        value = self.device_obj.status.get(self._color_temp_dpcode)
        if value is None:
            return None
        # Scale from device range to Kelvin range
        return self._scale(
            int(value),
            self._temp_min, self._temp_max,
            MIN_KELVIN, MAX_KELVIN,
        )

    @property
    def hs_color(self) -> tuple[float, float] | None:
        """Return the HS color."""
        if not self._color_data_dpcode:
            return None
        raw = self.device_obj.status.get(self._color_data_dpcode)
        if not raw:
            return None
        try:
            if isinstance(raw, str):
                color_data = json.loads(raw)
            else:
                color_data = raw
            h = color_data.get("h", 0)
            s = color_data.get("s", 0)
            # s is typically 0-1000 or 0-255, scale to 0-100
            s_max = 1000 if self._color_data_dpcode == DPCode.COLOUR_DATA_V2 else 255
            s_pct = (s / s_max) * 100
            return (h, s_pct)
        except (json.JSONDecodeError, TypeError, KeyError):
            return None

    @property
    def color_mode(self) -> ColorMode | None:
        """Return the current color mode."""
        if not self._attr_supported_color_modes:
            return None

        # Check work_mode to determine current mode
        if self._work_mode_dpcode:
            work_mode = self.device_obj.status.get(self._work_mode_dpcode, "")
            if work_mode == "colour" and (
                ColorMode.HS in self._attr_supported_color_modes
            ):
                return ColorMode.HS
            if work_mode == "white" and (
                ColorMode.COLOR_TEMP
                in self._attr_supported_color_modes
            ):
                return ColorMode.COLOR_TEMP

        # Default: return the "best" supported mode
        if ColorMode.HS in self._attr_supported_color_modes:
            return ColorMode.HS
        if ColorMode.COLOR_TEMP in self._attr_supported_color_modes:
            return ColorMode.COLOR_TEMP
        if ColorMode.BRIGHTNESS in self._attr_supported_color_modes:
            return ColorMode.BRIGHTNESS
        return ColorMode.ONOFF

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        commands: list[dict[str, Any]] = []

        if self._switch_dpcode:
            commands.append({"code": self._switch_dpcode, "value": True})

        # Handle brightness
        if ATTR_BRIGHTNESS in kwargs and self._brightness_dpcode:
            brightness = kwargs[ATTR_BRIGHTNESS]
            device_brightness = self._scale(
                brightness, 0, 255, self._bright_min, self._bright_max
            )
            commands.append(
                {"code": self._brightness_dpcode,
                 "value": device_brightness}
            )
            if self._work_mode_dpcode:
                commands.append({"code": self._work_mode_dpcode, "value": "white"})

        # Handle color temperature
        if ATTR_COLOR_TEMP_KELVIN in kwargs and self._color_temp_dpcode:
            kelvin = kwargs[ATTR_COLOR_TEMP_KELVIN]
            device_temp = self._scale(
                kelvin, MIN_KELVIN, MAX_KELVIN, self._temp_min, self._temp_max
            )
            commands.append({"code": self._color_temp_dpcode, "value": device_temp})
            if self._work_mode_dpcode:
                commands.append({"code": self._work_mode_dpcode, "value": "white"})

        # Handle HS color
        if ATTR_HS_COLOR in kwargs and self._color_data_dpcode:
            h, s = kwargs[ATTR_HS_COLOR]
            s_max = 1000 if self._color_data_dpcode == DPCode.COLOUR_DATA_V2 else 255
            v_max = 1000 if self._color_data_dpcode == DPCode.COLOUR_DATA_V2 else 255
            color_value = {
                "h": int(h),
                "s": int((s / 100) * s_max),
                "v": v_max,  # Full brightness in color mode
            }
            commands.append(
                {"code": self._color_data_dpcode, "value": json.dumps(color_value)}
            )
            if self._work_mode_dpcode:
                commands.append({"code": self._work_mode_dpcode, "value": "colour"})

        await self._send_commands(commands)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the light off."""
        if self._switch_dpcode:
            await self._send_commands([{"code": self._switch_dpcode, "value": False}])

    @staticmethod
    def _scale(
        value: float | int,
        from_min: float,
        from_max: float,
        to_min: float,
        to_max: float,
    ) -> int:
        """Scale a value from one range to another."""
        if from_max == from_min:
            return int(to_min)
        scaled = (value - from_min) / (from_max - from_min) * (to_max - to_min) + to_min
        return int(max(to_min, min(to_max, scaled)))
