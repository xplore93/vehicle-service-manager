"""Vehicle Service Manager integration."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers.event import async_track_state_change_event
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN, PLATFORMS,
    CONF_ENTITY_KM, CONF_KM, CONF_SERVICES, CONF_INTERVALS,
    HA_SERVICE_ADD_ENTRY, HA_SERVICE_UPDATE_KM,
    HA_SERVICE_ADD_REPAIR, HA_SERVICE_ADD_TIRE,
    SERVICE_HU, CONF_INITIAL_HU_DATE, CONF_INITIAL_HU_KM,
    EVENT_SERVICE_ENTRY_ADDED, EVENT_KM_UPDATED,
    ALL_SERVICE_IDS,
)
from .store import get_store, VehicleServiceStore

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

    # All config entries share ONE store instance
    store = get_store(hass)
    await store.async_load()

    vehicle_id: str = entry.data["vehicle_id"]

    # First-time: seed vehicle into store
    if store.get_vehicle(vehicle_id) is None:
        _LOGGER.info("Creating new vehicle %s in store", vehicle_id)
        vehicle_data = _build_initial_vehicle(entry.data)
        await store.async_add_vehicle(vehicle_id, vehicle_data)

        hu_date = entry.data.get(CONF_INITIAL_HU_DATE)
        if hu_date and SERVICE_HU in entry.data.get(CONF_SERVICES, []):
            hu_km = entry.data.get(CONF_INITIAL_HU_KM, 0)
            await store.async_add_service_entry(
                vehicle_id=vehicle_id,
                entry_date=hu_date,
                km=hu_km,
                services=[SERVICE_HU],
                notes="HU/AU – eingetragen bei Fahrzeuganlage",
                auto=True,
            )
    else:
        _LOGGER.debug("Vehicle %s already in store", vehicle_id)
        await _sync_entry_to_store(store, entry)

    hass.data[DOMAIN][entry.entry_id] = {"vehicle_id": vehicle_id}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register WebSocket + HA services once
    if not hass.data[DOMAIN].get("_ws_registered"):
        _register_websocket(hass)
        _register_services(hass)
        hass.data[DOMAIN]["_ws_registered"] = True

    # entity_km lives in entry.data (options flow reloads entry and writes back there)
    entity_km: str = (entry.data.get(CONF_ENTITY_KM) or "").strip()
    if entity_km:
        _setup_km_tracking(hass, entry, store, vehicle_id, entity_km)
        # Also read current state immediately so KM is correct right away
        state = hass.states.get(entity_km)
        if state and state.state not in ("unknown", "unavailable"):
            try:
                current_km = int(float(state.state))
                vehicle = store.get_vehicle(vehicle_id)
                if vehicle and current_km > (vehicle.get("km") or 0):
                    _spawn(hass, store.async_update_km(vehicle_id, current_km))
                    _LOGGER.info("Initial KM from entity %s: %d", entity_km, current_km)
            except (ValueError, TypeError):
                pass

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
    """Push edited config entry data into the shared store.

    The options flow writes to ``entry.data`` and reloads the entry, but the
    store is the single source of truth for entities, cards and services —
    so every setup must push entry.data into the store for existing vehicles.
    """
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
    hass: HomeAssistant, entry: ConfigEntry, store: VehicleServiceStore,
    vehicle_id: str, entity_id: str,
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
        # Higher wins — an OBD blip or odometer reset must not clobber the store
        vehicle = store.get_vehicle(vehicle_id)
        if vehicle is None or km <= (vehicle.get("km") or 0):
            return
        _spawn(hass, store.async_update_km(vehicle_id, km))
        hass.bus.async_fire(EVENT_KM_UPDATED, {"vehicle_id": vehicle_id, "km": km})

    entry.async_on_unload(
        async_track_state_change_event(hass, [entity_id], _on_km_state_change)
    )
    _LOGGER.debug("Tracking KM entity %s for vehicle %s", entity_id, vehicle_id)


# ── WebSocket API ─────────────────────────────────────────────────────────────

def _register_websocket(hass: HomeAssistant) -> None:

    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/vehicles"})
    @websocket_api.async_response
    async def ws_get_vehicles(hass, connection, msg):
        store = get_store(hass)
        await store.async_load()
        connection.send_result(msg["id"], {"vehicles": store.get_vehicles()})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/add_service_entry",
        vol.Required("vehicle_id"): str,
        vol.Required("entry_date"): str,
        vol.Required("km"): vol.Coerce(int),
        vol.Required("services"): vol.All(cv.ensure_list, [vol.In(ALL_SERVICE_IDS)]),
        vol.Optional("notes", default=""): str,
    })
    @websocket_api.async_response
    async def ws_add_service_entry(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        entry = await store.async_add_service_entry(
            vehicle_id=vid, entry_date=msg["entry_date"],
            km=msg["km"], services=msg["services"], notes=msg.get("notes", ""),
        )
        v = store.get_vehicle(vid)
        if v and msg["km"] > (v.get("km") or 0):
            await store.async_update_km(vid, msg["km"])
        connection.send_result(msg["id"], {"entry": entry, "vehicle": store.get_vehicle(vid)})
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_service_entry",
        vol.Required("vehicle_id"): str,
        vol.Required("entry_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    })
    @websocket_api.async_response
    async def ws_delete_service_entry(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_delete_service_entry(vid, msg["entry_index"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": store.get_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/add_repair",
        vol.Required("vehicle_id"): str,
        vol.Required("entry_date"): str,
        vol.Required("km"): vol.Coerce(int),
        vol.Required("category"): str,
        vol.Optional("description", default=""): str,
        vol.Optional("cost", default=0): vol.Coerce(float),
    })
    @websocket_api.async_response
    async def ws_add_repair(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_add_repair(vid, {
            "date": msg["entry_date"], "km": msg["km"],
            "cat": msg["category"], "desc": msg.get("description", ""),
            "cost": msg.get("cost", 0),
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": store.get_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_repair",
        vol.Required("vehicle_id"): str,
        vol.Required("repair_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    })
    @websocket_api.async_response
    async def ws_delete_repair(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_delete_repair(vid, msg["repair_index"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": store.get_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/add_tire",
        vol.Required("vehicle_id"): str,
        vol.Required("entry_date"): str,
        vol.Required("km"): vol.Coerce(int),
        vol.Required("tire_type"): str,
        vol.Required("axle"): str,
        vol.Optional("width"): vol.Coerce(int),
        vol.Optional("ratio"): vol.Coerce(int),
        vol.Optional("rim"): vol.Coerce(int),
        vol.Optional("brand", default=""): str,
        vol.Optional("dot", default=""): str,
        vol.Optional("vl", default=0.0): vol.Coerce(float),
        vol.Optional("vr", default=0.0): vol.Coerce(float),
        vol.Optional("hl", default=0.0): vol.Coerce(float),
        vol.Optional("hr", default=0.0): vol.Coerce(float),
    })
    @websocket_api.async_response
    async def ws_add_tire(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        tire = {
            "date": msg["entry_date"], "km": msg["km"],
            "type": msg["tire_type"], "axle": msg["axle"],
            "width": msg.get("width"), "ratio": msg.get("ratio"), "rim": msg.get("rim"),
            "brand": msg.get("brand", ""), "dot": msg.get("dot", ""),
            "vl": msg.get("vl", 0.0), "vr": msg.get("vr", 0.0),
            "hl": msg.get("hl", 0.0), "hr": msg.get("hr", 0.0),
        }
        await store.async_add_tire(vid, tire)
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": store.get_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/update_km",
        vol.Required("vehicle_id"): str,
        vol.Required("km"): vol.Coerce(int),
    })
    @websocket_api.async_response
    async def ws_update_km(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_update_km(vid, msg["km"])
        hass.bus.async_fire(EVENT_KM_UPDATED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"success": True})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_tire",
        vol.Required("vehicle_id"): str,
        vol.Required("tire_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    })
    @websocket_api.async_response
    async def ws_delete_tire(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_delete_tire(vid, msg["tire_index"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": store.get_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/update_service_entry",
        vol.Required("vehicle_id"): str,
        vol.Required("entry_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Required("entry_date"): str,
        vol.Required("km"): vol.Coerce(int),
        vol.Required("services"): vol.All(cv.ensure_list, [vol.In(ALL_SERVICE_IDS)]),
        vol.Optional("notes", default=""): str,
    })
    @websocket_api.async_response
    async def ws_update_service_entry(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_update_service_entry(
            vehicle_id=vid,
            entry_index=msg["entry_index"],
            entry_date=msg["entry_date"],
            km=msg["km"],
            services=msg["services"],
            notes=msg.get("notes", ""),
        )
        # Update km if higher
        v = store.get_vehicle(vid)
        if v and msg["km"] > (v.get("km") or 0):
            await store.async_update_km(vid, msg["km"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": store.get_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_vehicle",
        vol.Required("vehicle_id"): str,
    })
    @websocket_api.async_response
    async def ws_delete_vehicle(hass, connection, msg):
        store = get_store(hass)
        vid = msg["vehicle_id"]
        if store.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await store.async_remove_vehicle(vid)
        _LOGGER.info("Vehicle %s deleted via WebSocket", vid)
        connection.send_result(msg["id"], {"success": True, "deleted_id": vid})

    for fn in [
        ws_get_vehicles, ws_add_service_entry, ws_delete_service_entry,
        ws_add_repair, ws_delete_repair, ws_add_tire, ws_update_km,
        ws_delete_vehicle, ws_delete_tire, ws_update_service_entry,
    ]:
        websocket_api.async_register_command(hass, fn)


# ── HA Services (for automations) ─────────────────────────────────────────────

def _register_services(hass: HomeAssistant) -> None:
    if hass.services.has_service(DOMAIN, HA_SERVICE_ADD_ENTRY):
        return

    async def handle_add_entry(call: ServiceCall) -> None:
        store = get_store(hass)
        vid = call.data["vehicle_id"]
        await store.async_add_service_entry(
            vehicle_id=vid, entry_date=call.data["entry_date"],
            km=call.data["km"], services=call.data["services"],
            notes=call.data.get("notes", ""),
        )
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    hass.services.async_register(DOMAIN, HA_SERVICE_ADD_ENTRY, handle_add_entry,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("entry_date"): cv.string,
            vol.Required("km"): vol.Coerce(int),
            vol.Required("services"): vol.All(cv.ensure_list, [vol.In(ALL_SERVICE_IDS)]),
            vol.Optional("notes", default=""): cv.string,
        }))

    async def handle_update_km(call: ServiceCall) -> None:
        store = get_store(hass)
        vid = call.data["vehicle_id"]
        await store.async_update_km(vid, call.data["km"])
        hass.bus.async_fire(EVENT_KM_UPDATED, {"vehicle_id": vid})

    hass.services.async_register(DOMAIN, HA_SERVICE_UPDATE_KM, handle_update_km,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("km"): vol.Coerce(int),
        }))

    async def handle_add_repair(call: ServiceCall) -> None:
        store = get_store(hass)
        vid = call.data["vehicle_id"]
        await store.async_add_repair(vid, {
            "date": call.data["entry_date"], "km": call.data["km"],
            "cat": call.data["category"], "desc": call.data.get("description", ""),
            "cost": call.data.get("cost", 0),
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    hass.services.async_register(DOMAIN, HA_SERVICE_ADD_REPAIR, handle_add_repair,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("entry_date"): cv.string,
            vol.Required("km"): vol.Coerce(int),
            vol.Required("category"): cv.string,
            vol.Optional("description", default=""): cv.string,
            vol.Optional("cost", default=0): vol.Coerce(float),
        }))

    async def handle_add_tire(call: ServiceCall) -> None:
        store = get_store(hass)
        vid = call.data["vehicle_id"]
        await store.async_add_tire(vid, {
            "date": call.data["entry_date"], "km": call.data["km"],
            "type": call.data["type"], "axle": call.data["axle"],
            "width": call.data.get("width"), "ratio": call.data.get("ratio"),
            "rim": call.data.get("rim"),
            "brand": call.data.get("brand", ""), "dot": call.data.get("dot", ""),
            "vl": call.data.get("vl", 0.0), "vr": call.data.get("vr", 0.0),
            "hl": call.data.get("hl", 0.0), "hr": call.data.get("hr", 0.0),
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    hass.services.async_register(DOMAIN, HA_SERVICE_ADD_TIRE, handle_add_tire,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("entry_date"): cv.string,
            vol.Required("km"): vol.Coerce(int),
            vol.Required("type"): vol.In(["summer", "winter", "allseason"]),
            vol.Required("axle"): vol.In(["all", "front", "rear"]),
            vol.Optional("width"): vol.Coerce(int),
            vol.Optional("ratio"): vol.Coerce(int),
            vol.Optional("rim"): vol.Coerce(int),
            vol.Optional("brand", default=""): cv.string,
            vol.Optional("dot", default=""): cv.string,
            vol.Optional("vl", default=0.0): vol.Coerce(float),
            vol.Optional("vr", default=0.0): vol.Coerce(float),
            vol.Optional("hl", default=0.0): vol.Coerce(float),
            vol.Optional("hr", default=0.0): vol.Coerce(float),
        }))
