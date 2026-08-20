"""Service registration for Vehicle Service Manager."""
from __future__ import annotations

import logging
import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    ALL_SERVICE_IDS,
    HA_SERVICE_ADD_ENTRY,
    HA_SERVICE_UPDATE_KM,
    HA_SERVICE_ADD_REPAIR,
    HA_SERVICE_ADD_TIRE,
    EVENT_SERVICE_ENTRY_ADDED,
    EVENT_KM_UPDATED,
)
from .coordinator import VehicleServiceCoordinator

_LOGGER = logging.getLogger(__name__)


def async_register_services(hass: HomeAssistant) -> None:
    """Register Home Assistant services for Vehicle Service Manager."""
    if hass.services.has_service(DOMAIN, HA_SERVICE_ADD_ENTRY):
        return

    async def handle_add_entry(call: ServiceCall) -> None:
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = call.data["vehicle_id"]
        await coordinator.async_add_service_entry(
            vehicle_id=vid,
            entry_date=call.data["entry_date"],
            km=call.data["km"],
            services=call.data["services"],
            notes=call.data.get("notes", ""),
        )
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    hass.services.async_register(
        DOMAIN,
        HA_SERVICE_ADD_ENTRY,
        handle_add_entry,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("entry_date"): cv.string,
            vol.Required("km"): vol.Coerce(int),
            vol.Required("services"): vol.All(cv.ensure_list, [vol.In(ALL_SERVICE_IDS)]),
            vol.Optional("notes", default=""): cv.string,
        }),
    )

    async def handle_update_km(call: ServiceCall) -> None:
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = call.data["vehicle_id"]
        await coordinator.async_update_km(vid, call.data["km"])
        hass.bus.async_fire(EVENT_KM_UPDATED, {"vehicle_id": vid})

    hass.services.async_register(
        DOMAIN,
        HA_SERVICE_UPDATE_KM,
        handle_update_km,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("km"): vol.Coerce(int),
        }),
    )

    async def handle_add_repair(call: ServiceCall) -> None:
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = call.data["vehicle_id"]
        await coordinator.async_add_repair(vid, {
            "date": call.data["entry_date"],
            "km": call.data["km"],
            "cat": call.data["category"],
            "desc": call.data.get("description", ""),
            "cost": call.data.get("cost", 0),
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    hass.services.async_register(
        DOMAIN,
        HA_SERVICE_ADD_REPAIR,
        handle_add_repair,
        schema=vol.Schema({
            vol.Required("vehicle_id"): cv.string,
            vol.Required("entry_date"): cv.string,
            vol.Required("km"): vol.Coerce(int),
            vol.Required("category"): cv.string,
            vol.Optional("description", default=""): cv.string,
            vol.Optional("cost", default=0): vol.Coerce(float),
        }),
    )

    async def handle_add_tire(call: ServiceCall) -> None:
        coordinator = VehicleServiceCoordinator(hass)
        await coordinator.async_load()
        vid = call.data["vehicle_id"]
        await coordinator.async_add_tire(vid, {
            "date": call.data["entry_date"],
            "km": call.data["km"],
            "type": call.data["type"],
            "axle": call.data["axle"],
            "width": call.data.get("width"),
            "ratio": call.data.get("ratio"),
            "rim": call.data.get("rim"),
            "brand": call.data.get("brand", ""),
            "dot": call.data.get("dot", ""),
            "vl": call.data.get("vl", 0.0),
            "vr": call.data.get("vr", 0.0),
            "hl": call.data.get("hl", 0.0),
            "hr": call.data.get("hr", 0.0),
        })
        hass.bus.async_fire(EVENT_SERVICE_ENTRY_ADDED, {"vehicle_id": vid})

    hass.services.async_register(
        DOMAIN,
        HA_SERVICE_ADD_TIRE,
        handle_add_tire,
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
        }),
    )
