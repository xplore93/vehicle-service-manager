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
from .store import get_store, VehicleServiceStore

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for each selected service point."""
    store = get_store(hass)
    await store.async_load()
    vehicle_id: str = hass.data[DOMAIN][entry.entry_id]["vehicle_id"]
    vehicle = store.get_vehicle(vehicle_id)

    if vehicle is None:
        return

    entities: list[SensorEntity] = []

    for svc_id in vehicle.get("services", []):
        entities.append(ServiceStatusSensor(hass, store, vehicle_id, svc_id, entry))

    entities.append(KmSensor(hass, store, vehicle_id, entry))

    for pos in ["vl", "vr", "hl", "hr"]:
        entities.append(TireDepthSensor(hass, store, vehicle_id, pos, entry))

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

def _months_since(iso_date: str) -> float:
    """Return months elapsed since an ISO date string (HA timezone)."""
    try:
        d = date.fromisoformat(iso_date)
    except (ValueError, TypeError):
        return 0.0
    return (hass_dt.now().date() - d).days / 30.44


def _calc_pct(vehicle: dict, svc_id: str) -> tuple[float, float | None, float | None]:
    """Return (pct, km_left, months_left) — worst of km and time axes."""
    last = vehicle.get("lastService", {}).get(svc_id, {})
    intv = vehicle.get("intervals", {}).get(svc_id, {})
    ez_date: str | None = vehicle.get("ezDate")
    current_km: int = vehicle.get("km", 0)

    km_pct: float | None = None
    km_left: float | None = None
    time_pct: float | None = None
    months_left: float | None = None

    if intv.get("km"):
        base_km = last.get("km") or 0
        driven = current_km - base_km
        # Clamp: current km below the base km (odometer swap) must not go negative
        km_pct = min(100.0, max(0.0, round(driven / intv["km"] * 100, 1)))
        km_left = max(0.0, intv["km"] - driven)

    if intv.get("months"):
        base_date = last.get("date") or ez_date
        if base_date:
            ms = _months_since(base_date)
            time_pct = min(100.0, round(ms / intv["months"] * 100, 1))
            months_left = max(0.0, round(intv["months"] - ms, 1))
        else:
            time_pct = 0.0
            months_left = float(intv["months"])

    pct = (
        max(p for p in [km_pct, time_pct] if p is not None)
        if (km_pct is not None or time_pct is not None)
        else 0.0
    )
    return pct, km_left, months_left


def _status_from_pct(pct: float) -> str:
    if pct >= 100:
        return "overdue"
    if pct >= 90:
        return "due"
    if pct >= 70:
        return "soon"
    if pct >= 50:
        return "watch"
    return "ok"


def _device_info(store: VehicleServiceStore, vehicle_id: str) -> DeviceInfo:
    vehicle = store.get_vehicle(vehicle_id)
    make = vehicle.get("make", "") if vehicle else ""
    model = vehicle.get("model", "") if vehicle else ""
    info: dict[str, Any] = {
        "identifiers": {(DOMAIN, vehicle_id)},
        "name": f"{make} {model}".strip() or vehicle_id,
    }
    if make:
        info["manufacturer"] = make
    if model:
        info["model"] = model
    vin = (vehicle.get("vin") or "").strip() if vehicle else ""
    if vin:
        info["serial_number"] = vin
    return DeviceInfo(**info)


# ── Service status sensor ─────────────────────────────────────────────────────

class ServiceStatusSensor(SensorEntity):
    """Sensor reporting status/percentage for one service point."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:car-wrench"

    def __init__(
        self,
        hass: HomeAssistant,
        store: VehicleServiceStore,
        vehicle_id: str,
        svc_id: str,
        entry: ConfigEntry,
    ) -> None:
        self._store = store
        self._vehicle_id = vehicle_id
        self._svc_id = svc_id
        self._attr_unique_id = f"{vehicle_id}_{svc_id}_status"
        self._attr_translation_key = svc_id
        self._attr_native_value: str = "ok"
        self._extra: dict[str, Any] = {}

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._store, self._vehicle_id)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._extra

    async def async_update(self) -> None:
        """Update state — synchronous store read wrapped in async def."""
        vehicle = self._store.get_vehicle(self._vehicle_id)
        if vehicle is None:
            return

        pct, km_left, months_left = _calc_pct(vehicle, self._svc_id)
        status = _status_from_pct(pct)
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
        store: VehicleServiceStore,
        vehicle_id: str,
        entry: ConfigEntry,
    ) -> None:
        self._store = store
        self._vehicle_id = vehicle_id
        self._attr_unique_id = f"{vehicle_id}_km"
        self._attr_translation_key = "km"

    @property
    def device_info(self) -> DeviceInfo:
        return _device_info(self._store, self._vehicle_id)

    async def async_update(self) -> None:
        vehicle = self._store.get_vehicle(self._vehicle_id)
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
        store: VehicleServiceStore,
        vehicle_id: str,
        position: str,
        entry: ConfigEntry,
    ) -> None:
        self._store = store
        self._vehicle_id = vehicle_id
        self._position = position
        self._attr_unique_id = f"{vehicle_id}_tire_{position}"
        self._attr_translation_key = f"tire_{position}"
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
            return

        tires = vehicle.get("tires", [])
        if not tires:
            self._attr_native_value = None
            return

        # Latest entry that has a value for THIS position — an axle-only set
        # (e.g. rear tires swapped) must not shadow the previous full set
        latest: dict[str, Any] | None = None
        for tire in reversed(tires):
            if float(tire.get(self._position) or 0) > 0:
                latest = tire
                break
        if latest is None:
            self._attr_native_value = None
            return

        orig = float(latest.get(self._position) or 0)

        mounted_km = int(latest.get("km") or 0)
        current_km = vehicle.get("km", 0)
        driven = max(0, current_km - mounted_km)
        worn = round(max(0.0, orig - driven * TIRE_WEAR_PER_KM), 2)

        tire_type = latest.get("type", "summer")
        warn_mm = TIRE_WARN_WINTER_MM if tire_type in ("winter", "allseason") else TIRE_WARN_SUMMER_MM

        if worn <= TIRE_LEGAL_MIN_MM:
            status = "critical"
        elif worn <= warn_mm:
            status = "warning"
        else:
            status = "ok"

        self._attr_native_value = worn
        self._extra = {
            "original_depth_mm": orig,
            "mounted_km": mounted_km,
            "driven_km": driven,
            "status": status,
            "warn_limit_mm": warn_mm,
            "legal_min_mm": TIRE_LEGAL_MIN_MM,
            "tire_type": tire_type,
            "brand": latest.get("brand", ""),
            "size": f"{latest.get('width','')}/{latest.get('ratio','')} R{latest.get('rim','')}",
            "dot": latest.get("dot", ""),
        }
