"""Sensor platform for Vehicle Service Manager."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.util import dt as hass_dt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    DOMAIN,
    SCAN_INTERVAL,
    EVENT_SERVICE_ENTRY_ADDED, EVENT_KM_UPDATED,
    TIRE_WEAR_PER_KM, TIRE_WARN_SUMMER_MM, TIRE_WARN_WINTER_MM, TIRE_LEGAL_MIN_MM,
)
from .coordinator import VehicleServiceCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each selected service point."""
    coordinator = VehicleServiceCoordinator(hass)
    await coordinator.async_load()
    vehicle_id: str = hass.data[DOMAIN][entry.entry_id]["vehicle_id"]
    vehicle = coordinator.get_vehicle(vehicle_id)

    if vehicle is None:
        return

    entities: list[SensorEntity] = []

    for svc_id in vehicle.get("services", []):
        entities.append(ServiceStatusSensor(hass, coordinator, vehicle_id, svc_id, entry))

    entities.append(KmSensor(hass, coordinator, vehicle_id, entry))

    for pos in ["vl", "vr", "hl", "hr"]:
        entities.append(TireDepthSensor(hass, coordinator, vehicle_id, pos, entry))

    async_add_entities(entities, update_before_add=True)

    # Refresh all sensors when data changes, or on a fixed interval so
    # time-based services (HU, brake fluid, AC) go overdue while parked.
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


# ── Helpers ───────────────────────────────────────────────────────────────────

# ── Service status sensor ─────────────────────────────────────────────────────

class ServiceStatusSensor(SensorEntity):
    """Sensor reporting status/percentage for one service point."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:car-wrench"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: VehicleServiceCoordinator,
        vehicle_id: str,
        svc_id: str,
        entry: ConfigEntry,
    ) -> None:
        self.coordinator = coordinator
        self._vehicle_id = vehicle_id
        self._svc_id = svc_id
        self._attr_unique_id = f"{vehicle_id}_{svc_id}_status"
        self._attr_translation_key = svc_id
        self._attr_native_value: str = "ok"
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this vehicle."""
        return self.coordinator.get_vehicle_device_info(self._vehicle_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        """Update state."""
        vehicle = self.coordinator.get_vehicle(self._vehicle_id)
        if vehicle is None:
            return

        pct, km_left, months_left = self.coordinator.calc_service_pct(vehicle, self._svc_id)
        status = self.coordinator.get_status_from_pct(pct)
        self._attr_native_value = status

        last = vehicle.get("lastService", {}).get(self._svc_id, {})
        intv = vehicle.get("intervals", {}).get(self._svc_id, {})

        self._extra = {
            "vehicle_id": self._vehicle_id,
            "service_id": self._svc_id,
            "percentage": pct,
            "status": status,
            "last_service_date": last.get("date"),
            "last_service_km": last.get("km"),
            "km_left": km_left,
            "months_left": months_left,
            "interval_km": intv.get("km"),
            "interval_months": intv.get("months"),
        }


# ── KM sensor ─────────────────────────────────────────────────────────────────

class KmSensor(SensorEntity):
    """Sensor showing current KM reading for a vehicle."""

    _attr_has_entity_name = True
    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = "km"
    _attr_icon = "mdi:gauge"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: VehicleServiceCoordinator,
        vehicle_id: str,
        entry: ConfigEntry,
    ) -> None:
        self.coordinator = coordinator
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_km"
        self._attr_translation_key = "km"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this vehicle."""
        return self.coordinator.get_vehicle_device_info(self._vehicle_id)

    async def async_update(self) -> None:
        vehicle = self.coordinator.get_vehicle(self._vehicle_id)
        if vehicle:
            self._attr_native_value = vehicle.get("km", 0)


# ── Tire depth sensor ─────────────────────────────────────────────────────────

class TireDepthSensor(SensorEntity):
    """Sensor showing projected tread depth for one wheel position."""

    _attr_has_entity_name = True
    _attr_native_unit_of_measurement = "mm"
    _attr_icon = "mdi:tire"

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: VehicleServiceCoordinator,
        vehicle_id: str,
        position: str,
        entry: ConfigEntry,
    ) -> None:
        self.coordinator = coordinator
        self._vehicle_id = vehicle_id
        self._position = position
        self._attr_unique_id = f"{vehicle_id}_tire_{position}"
        self._attr_translation_key = f"tire_{position}"
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this vehicle."""
        return self.coordinator.get_vehicle_device_info(self._vehicle_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        vehicle = self.coordinator.get_vehicle(self._vehicle_id)
        if vehicle is None:
            return

        tire_data = self.coordinator.calc_tire_wear(vehicle, self._position)
        
        if not tire_data:
            self._attr_native_value = None
            return

        self._attr_native_value = tire_data["worn"]
        self._extra = {k: v for k, v in tire_data.items() if k != "worn"}
