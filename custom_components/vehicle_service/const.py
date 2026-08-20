"""Constants for Vehicle Service Manager."""
import json
import os
from datetime import timedelta

with open(os.path.dirname(os.path.abspath(__file__)) + "/manifest.json", "r") as f:
    manifest = json.load(f)
    versions = manifest["version"].split("-beta")[0].split(".")
    minor = int(versions[1])
    if minor < 10:
        minor = f"0{minor}"
    patch = int(versions[2])
    if patch < 10:
        patch = f"0{patch}"
    INTEGRATION_VERSION = int(f"{versions[0]}{minor}{patch}")

DOMAIN = "vehicle_service"
PLATFORMS = ["sensor", "binary_sensor"]

# Storage
STORAGE_VERSION = 1
STORAGE_KEY = "vehicle_service"

# Config flow keys
CONF_MAKE = "make"
CONF_MODEL = "model"
CONF_EZ_DATE = "ez_date"           # Erstzulassung ISO string
CONF_KM = "km"
CONF_PLATE = "plate"
CONF_VIN = "vin"
CONF_HSN = "hsn"
CONF_ENTITY_KM = "entity_km"       # optional HA entity for live KM reading
CONF_SERVICES = "services"         # list of selected service IDs
CONF_INTERVALS = "intervals"       # dict: {service_id: {km?: int, months?: int}}
CONF_INITIAL_HU_DATE = "initial_hu_date"
CONF_INITIAL_HU_KM = "initial_hu_km"

# Service IDs
SERVICE_OIL = "oil"
SERVICE_INSPECTION = "inspection"
SERVICE_BRAKE_FLUID = "brake_fluid"
SERVICE_CABIN_FILTER = "cabin_filter"
SERVICE_AIR_FILTER = "air_filter"
SERVICE_SPARK_PLUGS = "spark_plugs"
SERVICE_FUEL_FILTER = "fuel_filter"
SERVICE_GEARBOX = "gearbox"
SERVICE_HALDEX = "haldex"
SERVICE_AC = "ac"
SERVICE_HU = "hu"

ALL_SERVICE_IDS = [
    SERVICE_OIL,
    SERVICE_INSPECTION,
    SERVICE_BRAKE_FLUID,
    SERVICE_CABIN_FILTER,
    SERVICE_AIR_FILTER,
    SERVICE_SPARK_PLUGS,
    SERVICE_FUEL_FILTER,
    SERVICE_GEARBOX,
    SERVICE_HALDEX,
    SERVICE_AC,
    SERVICE_HU,
]

# Interval type: "km", "time", "both"
SERVICE_INTERVAL_TYPE = {
    SERVICE_OIL: "both",
    SERVICE_INSPECTION: "both",
    SERVICE_BRAKE_FLUID: "time",
    SERVICE_CABIN_FILTER: "both",
    SERVICE_AIR_FILTER: "both",
    SERVICE_SPARK_PLUGS: "both",
    SERVICE_FUEL_FILTER: "both",
    SERVICE_GEARBOX: "km",
    SERVICE_HALDEX: "both",
    SERVICE_AC: "time",
    SERVICE_HU: "time",
}

# Default intervals
DEFAULT_INTERVALS = {
    SERVICE_OIL:          {"km": 30000, "months": 24},
    SERVICE_INSPECTION:   {"km": 30000, "months": 12},
    SERVICE_BRAKE_FLUID:  {"months": 24},
    SERVICE_CABIN_FILTER: {"km": 60000, "months": 24},
    SERVICE_AIR_FILTER:   {"km": 90000, "months": 72},
    SERVICE_SPARK_PLUGS:  {"km": 60000, "months": 48},
    SERVICE_FUEL_FILTER:  {"km": 90000, "months": 72},
    SERVICE_GEARBOX:      {"km": 60000},
    SERVICE_HALDEX:       {"km": 40000, "months": 36},
    SERVICE_AC:           {"months": 24},
    SERVICE_HU:           {"months": 24},
}

# HA service call names
HA_SERVICE_ADD_ENTRY = "add_service_entry"
HA_SERVICE_UPDATE_KM = "update_km"
HA_SERVICE_ADD_REPAIR = "add_repair"
HA_SERVICE_ADD_TIRE = "add_tire"

# Events
EVENT_SERVICE_ENTRY_ADDED = f"{DOMAIN}_service_entry_added"
EVENT_KM_UPDATED = f"{DOMAIN}_km_updated"

# Periodic sensor refresh (time-based due dates tick down while the car is parked)
SCAN_INTERVAL = timedelta(hours=1)

# Tire wear: 1.5 mm per 10,000 km
TIRE_WEAR_PER_KM = 1.5 / 10000
TIRE_WARN_SUMMER_MM = 3.0
TIRE_WARN_WINTER_MM = 4.0
TIRE_LEGAL_MIN_MM = 1.6
