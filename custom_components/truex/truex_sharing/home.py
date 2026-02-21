"""TrueX home model.

Equivalent to tuya_sharing.home.SmartLifeHome.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SmartLifeHome:
    """Representation of a smart home."""

    home_id: str
    name: str
    geo_name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    role: str = ""

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> SmartLifeHome:
        """Create a SmartLifeHome from API response data."""
        return cls(
            home_id=str(data.get("home_id", "")),
            name=data.get("name", ""),
            geo_name=data.get("geo_name", ""),
            lat=data.get("lat", 0.0),
            lon=data.get("lon", 0.0),
            role=data.get("role", ""),
        )
