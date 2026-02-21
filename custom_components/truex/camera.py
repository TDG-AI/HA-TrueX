"""Support for TrueX cameras."""

from __future__ import annotations

import time

from homeassistant.components import ffmpeg
from homeassistant.components.camera import (
    Camera as CameraEntity,
    CameraEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
)
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from . import TrueXConfigEntry
from .const import DeviceCategory, LOGGER
from .entity import TrueXEntity
from .truex_sharing import CustomerDevice, Manager

CAMERA_CATEGORIES: set[str] = {
    DeviceCategory.SP,
    DeviceCategory.DGHSXJ,
}

STREAM_TYPE = "RTSP"
STREAM_URL_TTL = 55  # seconds


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueXConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up TrueX cameras."""
    truex_data = entry.runtime_data
    manager = truex_data.manager
    coordinator = truex_data.coordinator

    entities: list[TrueXCameraEntity] = []
    for device in manager.device_map.values():
        if device.category in CAMERA_CATEGORIES:
            entities.append(
                TrueXCameraEntity(coordinator, device, manager)
            )

    LOGGER.debug("Setting up %d camera entities", len(entities))
    async_add_entities(entities)


class TrueXCameraEntity(TrueXEntity, CameraEntity):
    """TrueX Camera Entity."""

    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_name = None

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        device: CustomerDevice,
        device_manager: Manager,
    ) -> None:
        """Init TrueX camera."""
        super().__init__(coordinator, device, device_manager)
        CameraEntity.__init__(self)
        self._attr_model = device.product_name or device.category
        self._stream_url: str | None = None
        self._stream_url_ts: float = 0.0

    async def _get_stream_url(self) -> str | None:
        """Get or refresh the stream URL."""
        now = time.monotonic()
        if (
            self._stream_url
            and now - self._stream_url_ts < STREAM_URL_TTL
        ):
            return self._stream_url

        url = await self.device_manager.get_device_stream_allocate(
            self.device_obj.id, STREAM_TYPE
        )
        if url:
            self._stream_url = url
            self._stream_url_ts = now
        else:
            self._stream_url = None
        return url

    async def stream_source(self) -> str | None:
        """Return the source of the stream."""
        return await self._get_stream_url()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image response from the camera."""
        stream_source = await self._get_stream_url()
        if not stream_source:
            return None
        return await ffmpeg.async_get_image(
            self.hass,
            stream_source,
            width=width,
            height=height,
        )
