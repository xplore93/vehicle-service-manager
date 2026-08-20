# Vehicle Service Manager for Home Assistant

Tracks service intervals, repairs and tire wear for your vehicles — as a native HA integration with real entities and a dedicated Lovelace card.

<p align="center">
  <a href="./README.md">English</a> ·
  <a href="./README.de.md">Deutsch</a>
</p>

---

## Features

- **Service status** with progress bar and traffic-light system (OK / Watch / Due soon / Due / Overdue)
- **First-registration date** as the starting point for time-based intervals until a service entry exists
- **HU/AU (MOT)** captured when the vehicle is created, with an automatic service entry
- **Live mileage** via any HA entity (OBD dongle, vehicle integration)
- **11 service points**: oil change, inspection, brake fluid, cabin filter, air filter, spark plugs, fuel filter, gearbox oil, Haldex oil, AC service, HU/AU (MOT)
- **Repairs & wear**: brakes, shock absorbers, timing belt, battery, clutch, and more
- **Tire tracking**: 4 wheel positions, tread depth, DOT age, wear projection (1.5 mm / 10,000 km)
- **Manufacturer logos** auto-detected (30+ brands)
- **Multiple vehicles** at once
- **Binary sensors** for automations (service due)
- **HA services** to add entries from automations

---

## Installation via HACS

### 1. Add the repository

1. Open HACS → **Integrations** → three dots → **Custom repositories**
2. URL: `https://github.com/toxictody1337/vehicle-service-manager`
   Category: **Integration**
3. **Add** → then search the HACS store and install
4. Restart Home Assistant

### 2. Set up the integration

**Settings → Devices & Services → + Add integration → "Vehicle Service Manager"**

The setup wizard walks through 3 steps:
1. **Vehicle data**: make, model, first registration, mileage, last HU/AU (MOT), optional live-mileage entity
2. **Service points**: choose which points to track
3. **Intervals**: adjust the km- and time-based intervals

> ⚠️ The default intervals are guidelines. Please check the service manual and adjust accordingly. When in doubt, ask your workshop. No liability for damage caused by incorrect values.

### 3. Add the Lovelace card set

The Lovelace card set is required to run the integration → https://github.com/toxictody1337/vehicle-service-card

The following entities are created per vehicle:

| Type | Example | Description |
|-----|----------|--------------|
| `sensor` | `sensor.golf_gti_oelwechsel` | Status: ok / watch / soon / due / overdue |
| `sensor` | `sensor.golf_gti_kilometerstand` | Current mileage |
| `sensor` | `sensor.golf_gti_reifen_vl` | Front-left tread depth in mm (projected) |
| `binary_sensor` | `sensor.golf_gti_oelwechsel_faellig` | True when ≥ 90% |
| `binary_sensor` | `sensor.golf_gti_service_faellig` | True when anything is ≥ 90% |

### Entity attributes

Each `sensor` entity has, among others, the following attributes:
```
vehicle_id, service_id, percentage, status, last_service_date,
last_service_km, km_left, months_left, interval_km, interval_months
```

---

## HA Services

### `vehicle_service.add_service_entry`
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
```yaml
service: vehicle_service.update_km
data:
  vehicle_id: "abc-123-uuid"
  km: 80000
```

### `vehicle_service.add_repair`
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
        entity_id: binary_sensor.golf_gti_service_faellig
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          title: "🔧 Service due"
          message: >
            {{ states('sensor.golf_gti_service_faellig') }} –
            Please book a service appointment.
```

### Automatic mileage pickup from an OBD integration
```yaml
# Alternative to configuring it in the integration:
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

The projected tread depth is calculated as:

```
current_depth = original_depth − (driven_km × 1.5 / 10.000)
```

Recommended wear limits:
- **Summer tires**: 3.0 mm
- **Winter / all-season tires**: 4.0 mm
- **Legal minimum**: 1.6 mm

---

## Notes & disclaimer

> The default intervals and calculations (tire wear, service due dates) are guidelines without warranty. Actual maintenance needs depend on the vehicle model, driving style and environmental conditions. Verify all values against the service manual and vehicle documentation. No liability for damage caused by incorrect values or incorrect interpretation of the displayed data.

---


---

## Development & attribution

This integration was developed with the help of **Claude (Anthropic AI)**.

### Third-party services used

| Service | Usage | License/Terms |
|--------|-----------|-------------------|
| [logo.dev](https://logo.dev) | Manufacturer logos for the vehicle cards | Free plan, own API key required |
| [Material Design Icons](https://materialdesignicons.com) | Icons via Home Assistant | Apache 2.0 |
| Home Assistant APIs | WebSocket, Config Flow, Storage | Apache 2.0 |

### logo.dev API key

The integration uses logo.dev for automatic manufacturer logos (Škoda, VW, BMW, etc.).
The key included in the code is a public demo key. For production use I recommend
creating your **own free account** at [logo.dev](https://logo.dev) and replacing the
key in the JS file:

```javascript
// In vehicle-service-card.js, line ~50:
function logoUrl(d) {
  return `https://img.logo.dev/${d}?token=YOUR_OWN_KEY&size=64&format=png`;
}
```

---

## License

MIT License – see [LICENSE](LICENSE)

> This software is provided without warranty. The interval values and calculations are
> guidelines without guarantee. Verify all values against your vehicle's service manual.
> No liability for damage caused by incorrect values or interpretation of the data.

## Contribute / Issues

Please report bugs or improvement suggestions as a [GitHub Issue](https://github.com/toxictody1337/vehicle-service-manager/issues).
