# Vehicle Service Manager for Home Assistant

Tracks service intervals, repairs and tire wear for your vehicles — as a native HA integration with real entities and a dedicated Lovelace card.

---

## Features

- **Service status** with progress and 5-level status (OK / Watch / Soon / Due / Overdue)
- **First registration date** as the starting point for time-based intervals until a service entry exists
- **HU/AU (MOT)** captured when the vehicle is created, with an automatic service entry
- **Live mileage** via any HA sensor entity (OBD dongle, vehicle integration)
- **11 service points**: oil change, inspection, brake fluid, cabin filter, air filter, spark plugs, fuel filter, gearbox oil, Haldex oil, AC service, HU/AU (MOT)
- **Repairs & wear**: brakes, discs, shock absorbers, timing belt, battery, clutch, and more
- **Tire tracking**: 4 wheel positions, tread depth, DOT age, wear projection (1.5 mm / 10,000 km)
- **Manufacturer logos** on the card (30+ brands)
- **Multiple vehicles** at once, with duplicate-plate/VIN guard
- **Binary sensors** for automations (single service due + overall "any due")
- **HA services** to add entries from automations
- **Editable via options flow** — all vehicle data, service selection and intervals can be changed after setup

> The Lovelace cards (`vehicle-service-card`, `vehicle-service-compact-card`) are bundled with the integration and auto-registered on setup — no extra card installation required.

---

## Service points & default intervals

| Service | ID | Default interval |
|---|---|---|
| Oil change | `oil` | 30,000 km / 24 months |
| Inspection | `inspection` | 30,000 km / 12 months |
| Brake fluid | `brake_fluid` | 24 months |
| Cabin filter | `cabin_filter` | 60,000 km / 24 months |
| Air filter | `air_filter` | 90,000 km / 72 months |
| Spark plugs (petrol) | `spark_plugs` | 60,000 km / 48 months |
| Fuel filter (diesel) | `fuel_filter` | 90,000 km / 72 months |
| Gearbox oil | `gearbox` | 60,000 km |
| Haldex oil (AWD) | `haldex` | 40,000 km / 36 months |
| AC service | `ac` | 24 months |
| HU/AU (MOT) | `hu` | 24 months |

> ⚠️ The default intervals are guidelines. Please check the service manual and adjust accordingly. When in doubt, ask your workshop. No liability for damage caused by incorrect values.

---

## Installation via HACS

### 1. Add the repositories

1. Open HACS → **Integrations** → three dots → **Custom repositories**
2. URL: `https://github.com/xplore93/vehicle-service-manager` — category: **Integration**
3. **Add** → then search the HACS store and install
4. Restart Home Assistant

**Requirements:** Home Assistant ≥ 2023.9.0.

### 2. Set up the integration

**Settings → Devices & Services → + Add integration → "Vehicle Service Manager"**

The setup wizard walks through 3 steps:

1. **Vehicle data** — make, model, first registration (month/year), current mileage, license plate, last HU/AU (MOT) with mileage, optional VIN / HSN, optional live-mileage entity
2. **Service points** — choose which points to track
3. **Intervals** — adjust the km- and time-based intervals (0 = not tracked)

The vehicle can be edited afterwards in the **options flow** (Settings → Devices & Services → ⋮ → Configure).

---

## Entities

One device per vehicle, with the following entities (names shown in English; they are translated per UI locale):

| Type | Example | Description |
|---|---|---|
| `sensor` | per service point (e.g. "Oil change") | Status: `ok` / `watch` / `soon` / `due` / `overdue` |
| `sensor` | "Mileage" | Current mileage (km) |
| `sensor` | "Tire front left" (and VR / HL / HR) | Projected tread depth (mm), or `unavailable` if no tire data exists |
| `binary_sensor` | per service point ("… due") | `on` when ≥ 90 % (due or overdue), device class `problem` |
| `binary_sensor` | "Service due" | `on` when any tracked point is ≥ 90 % |

### Status levels

| Status | Progress | Meaning |
|---|---|---|
| `ok` | < 50 % | No action needed |
| `watch` | 50 – 69 % | Keep an eye on it |
| `soon` | 70 – 89 % | Due soon |
| `due` | 90 – 99 % | Schedule it |
| `overdue` | ≥ 100 % | Overdue |

Progress is the worst of the km- and time-based axes; a service counts as due on **either** axis.

### Entity attributes

Service status sensors:

```
vehicle_id, service_id, percentage, status,
last_service_date, last_service_km, km_left, months_left,
interval_km, interval_months
```

Binary sensors: `service_id`, `percentage`, `status`, `km_left`, `months_left`
(the "Service due" sensor additionally reports `due_services` and `due_count`).

Tire sensors: `status` (`ok` / `warning` / `critical`), `original_depth_mm`,
`mounted_km`, `driven_km`, `warn_limit_mm`, `legal_min_mm`, `tire_type`,
`brand`, `size`, `dot`.

---

## HA services

### `vehicle_service.add_service_entry`

Adds a service entry to the vehicle history and updates the last-service date for the given service points.

```yaml
service: vehicle_service.add_service_entry
data:
  vehicle_id: "abc-123-uuid"
  entry_date: "2024-03-15"
  km: 79500
  services:
    - oil
    - inspection
  notes: "Independent workshop Musterstadt"
```

### `vehicle_service.update_km`

Updates the mileage of a vehicle. (If a live-KM entity is configured, the value is taken from it automatically.)

```yaml
service: vehicle_service.update_km
data:
  vehicle_id: "abc-123-uuid"
  km: 80000
```

### `vehicle_service.add_repair`

Adds a repair or wear entry. Categories: `brakes_front`, `brakes_rear`, `brakes_full`, `discs_front`, `discs_rear`, `shock_front`, `shock_rear`, `timing_belt`, `battery`, `clutch`, `other`.

```yaml
service: vehicle_service.add_repair
data:
  vehicle_id: "abc-123-uuid"
  entry_date: "2024-03-15"
  km: 79500
  category: brakes_front
  description: "Textar brake pads"
  cost: 180
```

### `vehicle_service.add_tire`

Records a tire set. Types: `summer`, `winter`, `allseason`. Axle: `all`, `front`, `rear`.

```yaml
service: vehicle_service.add_tire
data:
  vehicle_id: "abc-123-uuid"
  entry_date: "2024-04-01"
  km: 80000
  type: summer
  axle: all
  width: 205
  ratio: 55
  rim: 16
  brand: Michelin
  dot: "2323"
  vl: 8.0
  vr: 8.0
  hl: 8.0
  hr: 8.0
```

---

## Automations — examples

### Notification when a service is due

```yaml
automation:
  - alias: "Service due – notification"
    trigger:
      - platform: state
        entity_id: binary_sensor.<vehicle>_service_due
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "🔧 Service due"
          message: >
            Please book a service appointment.
```

### Automatic mileage pickup from an OBD integration

```yaml
# Alternative to configuring a live-KM entity in the integration:
automation:
  - alias: "Update mileage automatically"
    trigger:
      - platform: state
        entity_id: sensor.obd_odometer
    action:
      - service: vehicle_service.update_km
        data:
          vehicle_id: "abc-123-uuid"
          km: "{{ states('sensor.obd_odometer') | int }}"
```

---

## Tire wear calculation

The projected tread depth per wheel position is calculated as:

```
current_depth = original_depth − (driven_km × 1.5 / 10000)
```

i.e. 1.5 mm of tread per 10,000 km driven since mounting. Status thresholds:

| Type | Warning limit |
|---|---|
| Summer tires | 3.0 mm |
| Winter / all-season tires | 4.0 mm |
| Legal minimum (all) | 1.6 mm → status `critical` |

---

## Notes & disclaimer

> The default intervals and calculations (tire wear, service due dates) are guidelines without warranty. Actual maintenance needs depend on the vehicle model, driving style and environmental conditions. Verify all values against the service manual and vehicle documentation. No liability for damage caused by incorrect values or incorrect interpretation of the displayed data.

---

## Development & attribution

This integration was developed with the help of **Claude (Anthropic AI)**.

### Third-party services used

| Service | Usage | License/Terms |
|---|---|---|
| [Material Design Icons](https://materialdesignicons.com) | Icons via Home Assistant | Apache 2.0 |
| Home Assistant APIs | WebSocket, Config Flow, Storage | Apache 2.0 |

---

## License

MIT License – see [LICENSE](LICENSE)

> This software is provided without warranty. The interval values and calculations are
> guidelines without guarantee. Verify all values against your vehicle's service manual.
> No liability for damage caused by incorrect values or interpretation of the data.

## Contribute / Issues

Please report bugs or improvement suggestions as a [GitHub Issue](https://github.com/xplore93/vehicle-service-manager/issues).
