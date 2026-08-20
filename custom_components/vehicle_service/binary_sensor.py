"""Binary sensor platform for Vehicle Service Manager."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN, SCAN_INTERVAL, EVENT_SERVICE_ENTRY_ADDED, EVENT_KM_UPDATED
from .sensor import _calc_pct, _status_from_pct, _device_info
from .store import get_store, VehicleServiceStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up one binary sensor per service point + one overall sensor."""
    store = get_store(hass)
    await store.async_load()
    vehicle_id: str = hass.data[DOMAIN][entry.entry_id]["vehicle_id"]
    vehicle = store.get_vehicle(vehicle_id)

    if vehicle is None:
        return

    entities: list[BinarySensorEntity] = []

    for svc_id in vehicle.get("services", []):
        entities.append(ServiceDueSensor(store, vehicle_id, svc_id))

    entities.append(AnyServiceDueSensor(store, vehicle_id))

    async_add_entities(entities, update_before_add=True)

    # Refresh when data changes, or on a fixed interval so time-based
    # services (HU, brake fluid, AC) go overdue while parked.
    def _refresh_all() -> None:
        for entity in entities:
            entity.async_schedule_update_ha_state(force_refresh=True)

    @callback
    def _on_data_changed(event) -> None:
        if event.data.get("vehicle_id") == vehicle_id:
            _refresh_all()

    entry.async_on_unload(async_track_time_interval(hass, _refresh_all, SCAN_INTERVAL))
    entry.async_on_unload(hass.bus.async_listen(EVENT_SERVICE_ENTRY_ADDED, _on_data_changed))
    entry.async_on_unload(hass.bus.async_listen(EVENT_KM_UPDATED, _on_data_changed))


class ServiceDueSensor(BinarySensorEntity):
    """True when a service point is at ≥ 90% (due or overdue)."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(
        self,
        store: VehicleServiceStore,
        vehicle_id: str,
        svc_id: str,
    ) -> None:
        self._store = store
        self._vehicle_id = vehicle_id
        self._svc_id = svc_id
        self._attr_unique_id = f"{vehicle_id}_{svc_id}_due"
        self._attr_translation_key = svc_id
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._store, self._vehicle_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        vehicle = self._store.get_vehicle(self._vehicle_id)
        if vehicle is None:
            self._attr_is_on = False
            return

        pct, km_left, months_left = _calc_pct(vehicle, self._svc_id)
        self._attr_is_on = pct >= 90

        self._extra = {
            "service_id": self._svc_id,
            "percentage": pct,
            "status": _status_from_pct(pct),
            "km_left": km_left,
            "months_left": months_left,
        }


class AnyServiceDueSensor(BinarySensorEntity):
    """True when ANY service point is at ≥ 90%."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:car-wrench"

    def __init__(
        self,
        store: VehicleServiceStore,
        vehicle_id: str,
    ) -> None:
        self._store = store
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_any_due"
        self._attr_translation_key = "any_due"
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._store, self._vehicle_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        vehicle = self._store.get_vehicle(self._vehicle_id)
        if vehicle is None:
            self._attr_is_on = False
            return

        due_services = [
            svc_id
            for svc_id in vehicle.get("services", [])
            if _calc_pct(vehicle, svc_id)[0] >= 90
        ]

        self._attr_is_on = len(due_services) > 0
        self._extra = {
            "due_services": due_services,
            "due_count": len(due_services),
        }
