from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LGUS60TRConfigEntry
from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import LGUS60TRCoordinator


class LGUS60TREntity(CoordinatorEntity[LGUS60TRCoordinator]):
    """Base entity for one LG soundbar data point."""

    _attr_has_entity_name = True

    def __init__(self, entry: LGUS60TRConfigEntry, key: str) -> None:
        super().__init__(entry.runtime_data)
        address = entry.runtime_data.address
        device_id = entry.unique_id or address.replace(":", "").lower()
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            connections={(CONNECTION_BLUETOOTH, address)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=entry.title,
        )

    @property
    def available(self) -> bool:
        """Keep explicit controls available while the SPP session is released."""
        return self.coordinator.data is not None
