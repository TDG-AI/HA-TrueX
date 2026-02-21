"""TrueX device data model.

Equivalent to tuya_sharing.device.CustomerDevice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class DeviceFunction:
    """Device function specification."""

    code: str = ""
    type: str = ""
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceStatusRange:
    """Device status range specification."""

    code: str = ""
    type: str = ""
    values: dict[str, Any] = field(default_factory=dict)


@dataclass
class CustomerDevice:
    """Representation of a TrueX/Tuya device.

    Mirrors tuya_sharing.device.CustomerDevice interface.
    """

    id: str
    name: str
    category: str
    product_id: str
    product_name: str
    online: bool = False
    icon: str = ""
    ip: str = ""
    time_zone: str = ""
    local_key: str = ""
    sub: bool = False
    uuid: str = ""
    active_time: int = 0
    create_time: int = 0
    update_time: int = 0

    # Runtime data populated after fetching
    status: dict[str, Any] = field(default_factory=dict)
    functions: dict[str, dict[str, Any]] = field(default_factory=dict)
    status_range: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Flag to indicate entity setup is complete
    set_up: bool = False

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> CustomerDevice:
        """Create a CustomerDevice from API response data."""
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            category=data.get("category", ""),
            product_id=data.get("product_id", ""),
            product_name=data.get("product_name", ""),
            online=data.get("online", False),
            icon=data.get("icon", ""),
            ip=data.get("ip", ""),
            time_zone=data.get("time_zone", ""),
            local_key=data.get("local_key", ""),
            sub=data.get("sub", False),
            uuid=data.get("uuid", ""),
            active_time=data.get("active_time", 0),
            create_time=data.get("create_time", 0),
            update_time=data.get("update_time", 0),
        )
