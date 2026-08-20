# Changelog

## [1.1.2] - 2026-08-19

### Fixed
- Removed the dead Lovelace auto-registration (`CARD_RESOURCES` was never defined); it
  crashed on first vehicle setup. Cards are provided by the separate `vehicle-service-card` repo
- Options-flow edits (intervals, km, make/model) now reach the shared store on every setup,
  so editing settings actually changes the sensors
- Negative indices in the store (`history[-1]` mutation/pop) are now rejected; WS index
  commands validate `min=0`
- Time-based services (HU, brake fluid, AC) now tick down to overdue via an hourly refresh
- Listener/timer leaks fixed: all listeners and the refresh timer are unregistered on unload,
  so repeated options-flow saves no longer accumulate duplicates
- Every mutating path (WS + HA services) now fires the refresh event, so entities stay in sync
- KM state listener no longer clobbers the store with a lower value (higher wins)
- WS delete / update-km paths return a proper `not_found` error instead of a `KeyError`
- `services` list is validated against known service IDs (WS + HA service)
- `add_tire` HA service no longer stores a stray `vehicle_id` inside the tire record
- A corrupt `.storage` file no longer risks being silently overwritten with an empty store
- Tire sensors read the latest entry *for that position*, so an axle-only set doesn't shadow
  the previous full set
- Negative `km_pct` clamped to 0; VIN exposed as the device serial number
- Duplicate-vehicle guard: the config flow aborts (`already_configured`) on matching plate/VIN
- Migrated to `OptionsFlowWithReload` (HA floor raised to 2023.9.0)
- Date math uses the HA timezone; dropped the incorrect `integration_type: "hub"`

### Changed
- Entity names moved to translations (`_attr_translation_key`) with `en`/`de` locales

## [1.1.1]

- Manifest version bump (intended card-picker fix; not shipped via HACS, which ships the root
  `custom_components/` tree)

## [1.0.10]

- Lovelace cards moved to the separate `vehicle-service-card` repository (`www/` removed)

## [1.0.9]

- Lovelace card updates

## [1.0.8]

- First public release (integration + bundled Lovelace cards)

## [1.0.7] - 2026-05-29

### Added
- Initial release
- 11 service points with km and time intervals
- Correct due calculation from Erstzulassung (first registration date)
- Live KM reading via HA sensor entity (OBD, vehicle integrations)
- HU/AU capture during vehicle setup with automatic history entry
- Service history with edit and delete
- Repairs & wear tracking
- Tyre tracking with tread depth projection (1.5mm / 10,000km)
- Full Lovelace dashboard card (`vehicle-service-card`)
- Compact icon-strip Lovelace card (`vehicle-service-compact-card`)
- Binary sensors for automations
- HA services for automation-based entry creation
- Store cleanup on vehicle deletion
- 3-colour status system (green/yellow/red)
- Brand logos for 30+ manufacturers
- Multi-vehicle support
