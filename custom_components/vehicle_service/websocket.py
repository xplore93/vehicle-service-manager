"""WebSocket API handlers for Vehicle Service Manager."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    ALL_SERVICE_IDS,
    EVENT_SERVICE_ENTRY_ADDED,
    EVENT_KM_UPDATED,
)
from .coordinator import VehicleServiceCoordinator

_LOGGER = logging.getLogger(__name__)


def async_register_websocket(hass: HomeAssistant) -> None:
    """Register WebSocket commands for Vehicle Service Manager."""

    @websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/vehicles"})
    @websocket_api.async_response
    async def ws_get_vehicles(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        # Returns enriched vehicles (with service_reports and tire_reports)
        connection.send_result(msg["id"], {"vehicles": coordinator.get_vehicles()})

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
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        v = coordinator.get_vehicle(vid)
        if v is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        entry = await coordinator.async_add_service_entry(
            vehicle_id=vid,
            entry_date=msg["entry_date"],
            km=msg["km"],
            services=msg["services"],
            notes=msg.get("notes", ""),
        )
        if msg["km"] > (v.get("km") or 0):
            await coordinator.async_update_km(vid, msg["km"])
        
        # Return enriched vehicle
        connection.send_result(msg["id"], {
            "entry": entry, 
            "vehicle": coordinator.get_enriched_vehicle(vid)
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_service_entry",
        vol.Required("vehicle_id"): str,
        vol.Required("entry_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    })
    @websocket_api.async_response
    async def ws_delete_service_entry(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_delete_service_entry(vid, msg["entry_index"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": coordinator.get_enriched_vehicle(vid)})

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
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_add_repair(vid, {
            "date": msg["entry_date"],
            "km": msg["km"],
            "cat": msg["category"],
            "desc": msg.get("description", ""),
            "cost": msg.get("cost", 0),
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": coordinator.get_enriched_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_repair",
        vol.Required("vehicle_id"): str,
        vol.Required("repair_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    })
    @websocket_api.async_response
    async def ws_delete_repair(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_delete_repair(vid, msg["repair_index"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": coordinator.get_enriched_vehicle(vid)})

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
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        tire = {
            "date": msg["entry_date"],
            "km": msg["km"],
            "type": msg["tire_type"],
            "axle": msg["axle"],
            "width": msg.get("width"),
            "ratio": msg.get("ratio"),
            "rim": msg.get("rim"),
            "brand": msg.get("brand", ""),
            "dot": msg.get("dot", ""),
            "vl": msg.get("vl", 0.0),
            "vr": msg.get("vr", 0.0),
            "hl": msg.get("hl", 0.0),
            "hr": msg.get("hr", 0.0),
        }
        await coordinator.async_add_tire(vid, tire)
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": coordinator.get_enriched_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/update_km",
        vol.Required("vehicle_id"): str,
        vol.Required("km"): vol.Coerce(int),
    })
    @websocket_api.async_response
    async def ws_update_km(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_update_km(vid, msg["km"])
        hass.bus.async_fire(EVENT_KM_UPDATED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"success": True})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_tire",
        vol.Required("vehicle_id"): str,
        vol.Required("tire_index"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    })
    @websocket_api.async_response
    async def ws_delete_tire(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_delete_tire(vid, msg["tire_index"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": coordinator.get_enriched_vehicle(vid)})

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
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        v = coordinator.get_vehicle(vid)
        if v is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_update_service_entry(
            vehicle_id=vid,
            entry_index=msg["entry_index"],
            entry_date=msg["entry_date"],
            km=msg["km"],
            services=msg["services"],
            notes=msg.get("notes", ""),
        )
        if msg["km"] > (v.get("km") or 0):
            await coordinator.async_update_km(vid, msg["km"])
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})
        connection.send_result(msg["id"], {"vehicle": coordinator.get_enriched_vehicle(vid)})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/delete_vehicle",
        vol.Required("vehicle_id"): str,
    })
    @websocket_api.async_response
    async def ws_delete_vehicle(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        if coordinator.get_vehicle(vid) is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        await coordinator.async_remove_vehicle(vid)
        _LOGGER.info("Vehicle %s deleted via WebSocket", vid)
        connection.send_result(msg["id"], {"success": True, "deleted_id": vid})

    @websocket_api.websocket_command({
        vol.Required("type"): f"{DOMAIN}/get_export_data",
        vol.Required("vehicle_id"): str,
    })
    @websocket_api.async_response
    async def ws_get_export_data(hass, connection, msg):
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = msg["vehicle_id"]
        v = coordinator.get_vehicle(vid)
        if v is None:
            connection.send_error(msg["id"], "not_found", f"Vehicle {vid} not found")
            return
        
        # Prepare data for CSV export
        history = v.get("history", [])
        repairs = v.get("repairs", [])
        
        connection.send_result(msg["id"], {
            "history": history,
            "repairs": repairs,
            "vehicle_name": f"{v.get('make', '')} {v.get('model', '')}".strip() or vid
        })

    for fn in [
        ws_get_vehicles,
        ws_add_service_entry,
        ws_delete_service_entry,
        ws_add_repair,
        ws_delete_repair,
        ws_add_tire,
        ws_update_km,
        ws_delete_vehicle,
        ws_delete_tire,
        ws_update_service_entry,
        ws_get_export_data,
    ]:
        websocket_api.async_register_command(hass, fn)
