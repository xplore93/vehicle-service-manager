"""Persistent storage for Vehicle Service Manager.

A single shared store instance per HA instance is kept in hass.data[DOMAIN]["_store"].
Every config entry (= every vehicle) reads from and writes to this shared store so
there is exactly one in-memory dict and one .storage file.
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import DOMAIN, STORAGE_KEY, STORAGE_VERSION

_LOGGER = logging.getLogger(__name__)


def get_store(hass: HomeAssistant) -> "VehicleServiceStore":
    """Return (or create) the single shared store for this HA instance."""
    if "_store" not in hass.data.setdefault(DOMAIN, {}):
        hass.data[DOMAIN]["_store"] = VehicleServiceStore(hass)
    return hass.data[DOMAIN]["_store"]


class VehicleServiceStore:
    """Single shared store — holds ALL vehicles in one .storage file."""

    def __init__(self, hass: HomeAssistant) -> None:
        self._hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._data: dict[str, Any] = {"vehicles": {}}
        self._loaded = False

    async def async_load(self) -> None:
        if self._loaded:
            return
        try:
            stored = await self._store.async_load()
        except Exception as e:  # corrupt .storage file
            # Never mark as loaded and never save over it — refuse to run with
            # an empty store, or the next save would wipe the user's data.
            _LOGGER.critical(
                "Could not load vehicle service store (%s). Refusing to start "
                "with an empty store to avoid overwriting %s.",
                e, STORAGE_KEY,
            )
            raise
        if stored:
            self._data = stored
        else:
            self._data = {"vehicles": {}}
        self._loaded = True
        _LOGGER.debug(
            "Vehicle service store loaded – %d vehicle(s)",
            len(self._data.get("vehicles", {})),
        )

    async def async_save(self) -> None:
        await self._store.async_save(self._data)

    # ── Vehicle CRUD ──────────────────────────────────────────────────────────

    def get_vehicles(self) -> dict[str, Any]:
        return self._data.get("vehicles", {})

    def get_vehicle(self, vehicle_id: str) -> dict[str, Any] | None:
        return self._data.get("vehicles", {}).get(vehicle_id)

    async def async_add_vehicle(self, vehicle_id: str, vehicle_data: dict[str, Any]) -> None:
        self._data.setdefault("vehicles", {})[vehicle_id] = vehicle_data
        await self.async_save()

    async def async_update_vehicle(self, vehicle_id: str, updates: dict[str, Any]) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            raise KeyError(f"Vehicle {vehicle_id} not found")
        vehicle.update(updates)
        await self.async_save()

    async def async_remove_vehicle(self, vehicle_id: str) -> None:
        self._data.get("vehicles", {}).pop(vehicle_id, None)
        await self.async_save()

    # ── KM ────────────────────────────────────────────────────────────────────

    async def async_update_km(self, vehicle_id: str, km: int) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            return
        vehicle["km"] = km
        await self.async_save()

    # ── Service history ───────────────────────────────────────────────────────

    def get_history(self, vehicle_id: str) -> list[dict[str, Any]]:
        vehicle = self.get_vehicle(vehicle_id)
        return vehicle.get("history", []) if vehicle else []

    async def async_add_service_entry(
        self,
        vehicle_id: str,
        entry_date: str,
        km: int,
        services: list[str],
        notes: str = "",
        auto: bool = False,
    ) -> dict[str, Any]:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            raise KeyError(f"Vehicle {vehicle_id} not found")
        entry = {"date": entry_date, "km": km, "services": services, "notes": notes, "auto": auto}
        vehicle.setdefault("history", []).append(entry)
        await self.async_save()
        return entry

    async def async_update_service_entry(
        self, vehicle_id: str, entry_index: int, entry_date: str, km: int,
        services: list[str], notes: str = "",
    ) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            raise KeyError(f"Vehicle {vehicle_id} not found")
        history = vehicle.get("history", [])
        if not (0 <= entry_index < len(history)):
            raise IndexError("Entry index out of range")
        history[entry_index] = {
            "date": entry_date, "km": km, "services": services, "notes": notes,
            "auto": history[entry_index].get("auto", False),
        }
        await self.async_save()

    async def async_delete_service_entry(self, vehicle_id: str, entry_index: int) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            raise KeyError(f"Vehicle {vehicle_id} not found")
        history = vehicle.get("history", [])
        if 0 <= entry_index < len(history):
            history.pop(entry_index)
        await self.async_save()

    # ── Repairs ───────────────────────────────────────────────────────────────

    def get_repairs(self, vehicle_id: str) -> list[dict[str, Any]]:
        vehicle = self.get_vehicle(vehicle_id)
        return vehicle.get("repairs", []) if vehicle else []

    async def async_add_repair(self, vehicle_id: str, repair: dict[str, Any]) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            raise KeyError(f"Vehicle {vehicle_id} not found")
        vehicle.setdefault("repairs", []).append(repair)
        await self.async_save()

    async def async_delete_repair(self, vehicle_id: str, repair_index: int) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            return
        repairs = vehicle.get("repairs", [])
        if 0 <= repair_index < len(repairs):
            repairs.pop(repair_index)
        await self.async_save()

    # ── Tires ─────────────────────────────────────────────────────────────────

    def get_tires(self, vehicle_id: str) -> list[dict[str, Any]]:
        vehicle = self.get_vehicle(vehicle_id)
        return vehicle.get("tires", []) if vehicle else []

    async def async_add_tire(self, vehicle_id: str, tire: dict[str, Any]) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            raise KeyError(f"Vehicle {vehicle_id} not found")
        vehicle.setdefault("tires", []).append(tire)
        await self.async_save()

    async def async_delete_tire(self, vehicle_id: str, tire_index: int) -> None:
        vehicle = self.get_vehicle(vehicle_id)
        if vehicle is None:
            return
        tires = vehicle.get("tires", [])
        if 0 <= tire_index < len(tires):
            tires.pop(tire_index)
        await self.async_save()
