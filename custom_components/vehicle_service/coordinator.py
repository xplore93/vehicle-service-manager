"""Coordinator for Vehicle Service Manager."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo

from .const import (
    DOMAIN,
    TIRE_WEAR_PER_KM,
    TIRE_WARN_SUMMER_MM,
    TIRE_WARN_WINTER_MM,
    TIRE_LEGAL_MIN_MM,
)
from .store import VehicleServiceStore, get_store

_LOGGER = logging.getLogger(__name__)


class VehicleServiceCoordinator:
    """Class to manage the vehicle service data and business logic."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self.store: VehicleServiceStore = get_store(hass)

    async def async_load(self) -> None:
        await self.store.async_load()

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any] | None:
        """Get vehicle by ID."""
        return self.store.get_vehicle(vehicle_id)

    def get_vehicles(self) -> dict[str, Any]:
        """Get all vehicles with enriched calculation data."""
        vehicles = self.store.get_vehicles()
        enriched = {}
        for vid, data in vehicles.items():
            enriched[vid] = self.get_enriched_vehicle(vid)
        return enriched

    def get_enriched_vehicle(self, vehicle_id: str) -> dict[str, Any] | None:
        """Get a vehicle with calculated service and tire data attached."""
        vehicle = self.get_vehicle(vehicle_id)
        if not vehicle:
            return None
        
        # Deep copy or at least don't mutate store original
        v = dict(vehicle)
        
        # Add calculated service data
        service_reports = {}
        for svc_id in v.get("services", []):
            pct, km_left, months_left = self.calc_service_pct(v, svc_id)
            service_reports[svc_id] = {
                "pct": pct,
                "km_left": km_left,
                "months_left": months_left,
                "status": self.get_status_from_pct(pct)
            }
        v["service_reports"] = service_reports
        
        # Add calculated tire data
        tire_reports = {}
        for pos in ["vl", "vr", "hl", "hr"]:
            report = self.calc_tire_wear(v, pos)
            if report:
                tire_reports[pos] = report
        v["tire_reports"] = tire_reports
        
        return v

    def get_vehicle_device_info(self, vehicle_id: str) -> DeviceInfo:
        """Get shared device info for vehicle entities."""
        vehicle = self.get_vehicle(vehicle_id) or {}
        make = vehicle.get("make", "")
        model = vehicle.get("model", "")
        info: dict[str, Any] = {
            "identifiers": {(DOMAIN, vehicle_id)},
            "name": f"{make} {model}".strip() or vehicle_id,
        }
        if make:
            info["manufacturer"] = make
        if model:
            info["model"] = model
        if vin := (vehicle.get("vin") or "").strip():
            info["serial_number"] = vin
        return DeviceInfo(**info)

    def recalc_last_service(self, vehicle: dict[str, Any]) -> dict[str, Any]:
        """Recalculate last service mapping for each service ID from history."""
        history = vehicle.get("history", [])
        last_service: dict[str, Any] = {}
        for entry in history:
            km = entry.get("km") or 0
            entry_date = entry.get("date")
            for svc_id in entry.get("services", []):
                current = last_service.get(svc_id, {})
                if not current or km >= (current.get("km") or 0):
                    last_service[svc_id] = {"km": km, "date": entry_date}
        vehicle["lastService"] = last_service
        return last_service

    async def async_add_service_entry(
        self,
        vehicle_id: str,
        entry_date: str,
        km: int,
        services: list[str],
        notes: str = "",
        auto: bool = False,
    ) -> dict[str, Any]:
        """Add service entry and update last service calculation."""
        entry = await self.store.async_add_service_entry(
            vehicle_id=vehicle_id,
            entry_date=entry_date,
            km=km,
            services=services,
            notes=notes,
            auto=auto,
        )
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle:
            self.recalc_last_service(vehicle)
            await self.store.async_save()
        return entry

    async def async_update_service_entry(
        self,
        vehicle_id: str,
        entry_index: int,
        entry_date: str,
        km: int,
        services: list[str],
        notes: str = "",
    ) -> None:
        """Update service entry and recalculate last service."""
        await self.store.async_update_service_entry(
            vehicle_id=vehicle_id,
            entry_index=entry_index,
            entry_date=entry_date,
            km=km,
            services=services,
            notes=notes,
        )
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle:
            self.recalc_last_service(vehicle)
            await self.store.async_save()

    async def async_delete_service_entry(self, vehicle_id: str, entry_index: int) -> None:
        """Delete service entry and recalculate last service."""
        await self.store.async_delete_service_entry(vehicle_id, entry_index)
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle:
            self.recalc_last_service(vehicle)
            await self.store.async_save()

    async def async_update_km(self, vehicle_id: str, km: int) -> None:
        """Update vehicle mileage."""
        await self.store.async_update_km(vehicle_id, km)

    async def async_add_repair(self, vehicle_id: str, repair: dict[str, Any]) -> None:
        """Add repair entry."""
        await self.store.async_add_repair(vehicle_id, repair)

    async def async_delete_repair(self, vehicle_id: str, repair_index: int) -> None:
        """Delete repair entry."""
        await self.store.async_delete_repair(vehicle_id, repair_index)

    async def async_add_tire(self, vehicle_id: str, tire: dict[str, Any]) -> None:
        """Add tire entry."""
        await self.store.async_add_tire(vehicle_id, tire)

    async def async_delete_tire(self, vehicle_id: str, tire_index: int) -> None:
        """Delete tire entry."""
        await self.store.async_delete_tire(vehicle_id, tire_index)

    async def async_remove_vehicle(self, vehicle_id: str) -> None:
        """Remove vehicle."""
        await self.store.async_remove_vehicle(vehicle_id)

    def calc_service_pct(self, vehicle: dict, svc_id: str) -> tuple[float, float | None, float | None]:
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
            km_pct = min(100.0, max(0.0, round(driven / intv["km"] * 100, 1)))
            km_left = max(0.0, intv["km"] - driven)

        if intv.get("months"):
            base_date = last.get("date") or ez_date
            if base_date:
                from homeassistant.util import dt as hass_dt
                from datetime import date
                try:
                    d = date.fromisoformat(base_date)
                    ms = (hass_dt.now().date() - d).days / 30.44
                except (ValueError, TypeError):
                    ms = 0.0
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

    def get_status_from_pct(self, pct: float) -> str:
        if pct >= 100:
            return "overdue"
        if pct >= 90:
            return "due"
        if pct >= 70:
            return "soon"
        if pct >= 50:
            return "watch"
        return "ok"

    def calc_tire_wear(self, vehicle: dict, position: str) -> dict[str, Any] | None:
        """Calculate tire wear for a specific position."""
        tires = vehicle.get("tires", [])
        if not tires:
            return None

        latest: dict[str, Any] | None = None
        for tire in reversed(tires):
            if float(tire.get(position) or 0) > 0:
                latest = tire
                break

        if latest is None:
            return None

        orig = float(latest.get(position) or 0)
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

        return {
            "worn": worn,
            "status": status,
            "original_depth_mm": orig,
            "mounted_km": mounted_km,
            "driven_km": driven,
            "warn_limit_mm": warn_mm,
            "legal_min_mm": TIRE_LEGAL_MIN_MM,
            "tire_type": tire_type,
            "brand": latest.get("brand", ""),
            "size": f"{latest.get('width','')}/{latest.get('ratio','')} R{latest.get('rim','')}",
            "dot": latest.get("dot", ""),
        }
