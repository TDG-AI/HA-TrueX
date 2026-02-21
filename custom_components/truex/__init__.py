"""Support for TrueX Smart Home devices."""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from typing_extensions import TypeAlias

from .truex_sharing import (
    CustomerApi,
    Manager,
    TrueXAPIError,
    TrueXTokenInfo,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONF_API_URL,
    CONF_CLIENT_ID,
    CONF_SCHEMA,
    CONF_SECRET,
    CONF_TOKEN_INFO,
    CONF_UID,
    DOMAIN,
    LOGGER,
    PLATFORMS,
    POLL_INTERVAL,
)

# Suppress overly verbose logs
logging.getLogger("aiohttp").setLevel(logging.WARNING)

TrueXConfigEntry: TypeAlias = ConfigEntry["TrueXData"]


class TrueXData:
    """TrueX data stored in the Home Assistant config entry."""

    def __init__(
        self,
        api: CustomerApi,
        manager: Manager,
        coordinator: DataUpdateCoordinator,
    ) -> None:
        """Initialize TrueXData."""
        self.api = api
        self.manager = manager
        self.coordinator = coordinator


async def async_setup_entry(hass: HomeAssistant, entry: TrueXConfigEntry) -> bool:
    """Set up TrueX from a config entry."""
    api_url = entry.data[CONF_API_URL]
    client_id = entry.data[CONF_CLIENT_ID]
    secret = entry.data[CONF_SECRET]
    schema = entry.data[CONF_SCHEMA]
    uid = entry.data[CONF_UID]
    token_data = entry.data.get(CONF_TOKEN_INFO)

    # Create API client
    api = CustomerApi(api_url, client_id, secret, schema)

    # Restore token if available
    if token_data:
        api.token_info = TrueXTokenInfo.from_dict(token_data)

    # Authenticate
    try:
        await api.get_access_token()
    except TrueXAPIError as exc:
        await api.close()
        raise ConfigEntryAuthFailed(
            f"Authentication failed: {exc}"
        ) from exc

    # Save refreshed token back
    _update_token_in_entry(hass, entry, api)

    # Create device manager
    manager = Manager(api, uid)

    # Fetch initial device cache
    try:
        await manager.update_device_cache()
    except Exception as exc:
        await api.close()
        raise ConfigEntryAuthFailed(
            f"Failed to fetch devices: {exc}"
        ) from exc

    # Create polling coordinator
    async def _async_update_data() -> dict[str, Any]:
        """Poll device status."""
        try:
            await manager.update_device_status()
            _update_token_in_entry(hass, entry, api)
        except TrueXAPIError as exc:
            raise UpdateFailed(f"Error polling TrueX: {exc}") from exc
        return {}

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name=f"{DOMAIN}_{uid}",
        update_method=_async_update_data,
        update_interval=timedelta(seconds=POLL_INTERVAL),
    )

    # Do an initial poll
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = TrueXData(api=api, manager=manager, coordinator=coordinator)

    # Register devices in the device registry
    device_registry = dr.async_get(hass)
    for device in manager.device_map.values():
        LOGGER.debug(
            "Register device %s (online: %s, category: %s): status=%s",
            device.id,
            device.online,
            device.category,
            device.status,
        )
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            identifiers={(DOMAIN, device.id)},
            manufacturer="TrueDigital",
            name=device.name,
            model=device.product_name or device.category,
            model_id=device.product_id,
        )

    # Forward setup to platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: TrueXConfigEntry) -> bool:
    """Unload a TrueX config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        truex_data = entry.runtime_data
        await truex_data.api.close()
    return unload_ok


def _update_token_in_entry(
    hass: HomeAssistant, entry: ConfigEntry, api: CustomerApi
) -> None:
    """Save the current token info back to the config entry."""
    new_data = {**entry.data, CONF_TOKEN_INFO: api.token_info.to_dict()}
    hass.config_entries.async_update_entry(entry, data=new_data)
