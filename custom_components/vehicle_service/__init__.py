"""Vehicle Service Manager integration."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

from .const import (
    DOMAIN, PLATFORMS,
    CONF_ENTITY_KM, CONF_KM, CONF_SERVICES,
    SERVICE_HU, CONF_INITIAL_HU_DATE, CONF_INITIAL_HU_KM,
    EVENT_KM_UPDATED,
    INTEGRATION_VERSION,
)
from .coordinator import VehicleServiceCoordinator
from .services import async_register_services
from .store import get_store, VehicleServiceStore
from .websocket import async_register_websocket

_LOGGER = logging.getLogger(__name__)

# Keep references to fire-and-forget tasks so they aren't garbage-collected mid-flight
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def _spawn(hass: HomeAssistant, coro) -> None:
    """Schedule a coroutine without awaiting it, retaining a task reference."""
    task = hass.async_create_task(coro)
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one vehicle from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = VehicleServiceCoordinator(hass)
    await coordinator.async_load()

    vehicle_id: str = entry.data["vehicle_id"]

    # First-time: seed vehicle into store
    if coordinator.get_vehicle(vehicle_id) is None:
        _LOGGER.info("Creating new vehicle %s in store", vehicle_id)
        vehicle_data = _build_initial_vehicle(entry.data)
        await coordinator.store.async_add_vehicle(vehicle_id, vehicle_data)

        hu_date = entry.data.get(CONF_INITIAL_HU_DATE)
        if hu_date and SERVICE_HU in entry.data.get(CONF_SERVICES, []):
            hu_km = entry.data.get(CONF_INITIAL_HU_KM, 0)
            await coordinator.async_add_service_entry(
                vehicle_id=vehicle_id,
                entry_date=hu_date,
                km=hu_km,
                services=[SERVICE_HU],
                notes="HU/AU – eingetragen bei Fahrzeuganlage",
                auto=True,
            )
    else:
        _LOGGER.debug("Vehicle %s already in store", vehicle_id)
        await _sync_entry_to_store(coordinator.store, entry)

    hass.data[DOMAIN][entry.entry_id] = {"vehicle_id": vehicle_id}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register WebSocket + HA services once
    if not hass.data[DOMAIN].get("_ws_registered"):
        async_register_websocket(hass)
        async_register_services(hass)
        hass.data[DOMAIN]["_ws_registered"] = True

    # entity_km lives in entry.data (options flow reloads entry and writes back there)
    entity_km: str = (entry.data.get(CONF_ENTITY_KM) or "").strip()
    if entity_km:
        _setup_km_tracking(hass, entry, coordinator, vehicle_id, entity_km)
        # Also read current state immediately so KM is correct right away
        state = hass.states.get(entity_km)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                current_km = int(float(state.state))
                vehicle = coordinator.get_vehicle(vehicle_id)
                if vehicle and current_km > (vehicle.get("km") or 0):
                    _spawn(hass, coordinator.async_update_km(vehicle_id, current_km))
                    _LOGGER.info("Initial KM from entity %s: %d", entity_km, current_km)
            except (ValueError, TypeError):
                pass

    url = f"/vehicle_service/{INTEGRATION_VERSION}/vehicle-service-card.js"
    if url not in hass.data["frontend_extra_module_url"].urls:
        file_path = os.path.join(os.path.dirname(__file__), "frontend", "vehicle-service-card.js")
        await hass.http.async_register_static_paths([StaticPathConfig(url, str(file_path), False)])
        add_extra_js_url(hass, url)

    return True


# ── Config entry → store sync ─────────────────────────────────────────────────

# entry.data key → store field key
_ENTRY_FIELD_MAP: dict[str, str] = {
    "make": "make",
    "model": "model",
    "ez_date": "ezDate",
    "plate": "plate",
    "vin": "vin",
    "hsn": "hsn",
    "entity_km": "entity",
    "services": "services",
    "intervals": "intervals",
}


async def _sync_entry_to_store(store: VehicleServiceStore, entry: ConfigEntry) -> None:
    """Push edited config entry data into the shared store."""
    vehicle_id = entry.data.get("vehicle_id", "")
    vehicle = store.get_vehicle(vehicle_id)
    if vehicle is None:
        return

    updates: dict[str, Any] = {}
    for data_key, store_key in _ENTRY_FIELD_MAP.items():
        if data_key in entry.data and vehicle.get(store_key) != entry.data[data_key]:
            updates[store_key] = entry.data[data_key]

    # KM: higher wins — a live reading must not be clobbered by a stale entry value
    entry_km = int(entry.data.get(CONF_KM) or 0)
    if entry_km > (vehicle.get("km") or 0):
        updates["km"] = entry_km

    if updates:
        await store.async_update_vehicle(vehicle_id, updates)
        _LOGGER.info("Synced options to store for %s: %s", vehicle_id, sorted(updates))


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean up store data when a config entry (vehicle) is deleted."""
    vehicle_id: str = entry.data.get("vehicle_id", "")
    if not vehicle_id:
        return
    store = get_store(hass)
    await store.async_load()
    if store.get_vehicle(vehicle_id) is not None:
        await store.async_remove_vehicle(vehicle_id)
        _LOGGER.info("Vehicle %s removed from store after entry deletion", vehicle_id)


# ── Build initial vehicle dict ────────────────────────────────────────────────

def _build_initial_vehicle(data: dict[str, Any]) -> dict[str, Any]:
    selected: list[str] = data.get(CONF_SERVICES, [])
    intervals: dict[str, dict] = data.get(CONF_INTERVALS, {})
    last_service = {sid: {"km": None, "date": None} for sid in selected}
    return {
        "make":        data.get("make", ""),
        "model":       data.get("model", ""),
        "ezDate":      data.get("ez_date"),
        "km":          data.get("km", 0),
        "plate":       data.get("plate", ""),
        "vin":         data.get("vin", ""),
        "hsn":         data.get("hsn", ""),
        "entity":      data.get("entity_km", ""),
        "services":    selected,
        "intervals":   intervals,
        "lastService": last_service,
        "history":     [],
        "repairs":     [],
        "tires":       [],
    }


# ── Live KM tracking ──────────────────────────────────────────────────────────

def _setup_km_tracking(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: VehicleServiceCoordinator,
    vehicle_id: str,
    entity_id: str,
) -> None:
    @callback
    def _on_km_state_change(event) -> None:
        new_state = event.data.get("new_state")
        if new_state is None:
            return
        try:
            km = int(float(new_state.state))
        except (ValueError, TypeError):
            return
        vehicle = coordinator.get_vehicle(vehicle_id)
        if vehicle is None or km <= (vehicle.get("km") or 0):
            return
        _spawn(hass, coordinator.async_update_km(vehicle_id, km))
        hass.bus.async_fire(EVENT_KM_UPDATED, {"vehicle_id": vehicle_id, "km": km})

    entry.async_on_unload(
        async_track_state_change_event(hass, [entity_id], _on_km_state_change)
    )
    _LOGGER.debug("Tracking KM entity %s for vehicle %s", entity_id, vehicle_id)
