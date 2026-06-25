# netbox-wireless-circuits

A NetBox 4.5 plugin for tracking licensed **microwave** and **millimeter-wave**
wireless links as native NetBox **Circuits**, with normalized plugin models for
license / PCN information, RF endpoint engineering, and modulation design intent.

## 1. Overview

This plugin treats each wireless link as a native `circuits.Circuit` (so it
inherits NetBox status, tenancy, terminations, change logging, and the circuits
UI) and attaches three plugin models that hold the *licensed / engineered
intent*:

- **Wireless License Profile** — one profile per Circuit. License / PCN / FCC
  registration workflow plus path engineering (band, channel plan, path length,
  losses, receiver threshold).
- **Wireless Circuit Endpoint** — RF and site engineering for each end of the
  path. Sides are labeled **A** and **Z** to match native circuit terminations.
  Optionally linked to NetBox `Site`, `Device`, and `Interface` objects.
- **Wireless Modulation Target** — the expected adaptive-modulation ladder and
  alarm thresholds, **per direction** (`A_TO_Z`, `Z_TO_A`).

NetBox is the **system of record for expected / licensed values**. Zabbix
consumes the plugin REST API and compares live radio telemetry against this
design intent. **Alarm logic lives in Zabbix, not in NetBox.**

## 2. Install

From the plugin source directory (the directory containing `pyproject.toml`),
install into the NetBox virtual environment:

```bash
pip install -e .
```

Add the plugin to NetBox `configuration.py`:

```python
PLUGINS = [
    "netbox_wireless_circuits",
]
```

Apply migrations and restart services:

```bash
python manage.py migrate
sudo systemctl restart netbox netbox-rq
```

## 3. Operating Model

1. **Create Circuit Types** (DCIM/Circuits → Circuit Types), e.g.:
   - `Licensed Microwave` (an existing type, id 69, may already be `Microwave`)
   - `Licensed Millimeter Wave`
   - optionally `Unlicensed Wireless Backhaul`
2. **Create a wireless provider / license context** (Circuits → Providers),
   e.g. `Comsearch`, `FCC/ULS`, or `internal engineering`.
3. **Create a native NetBox Circuit** with the appropriate CID and type.
4. From the Circuit's **`Wireless License`** tab, **add the wireless profile**.
5. **Add A / Z endpoints** with site / device / interface links and RF data.
6. **Add modulation targets** manually or via CSV import.

Status conventions:

- Use the **native Circuit status** for operational state: `active`, `planned`,
  `offline`, `decommissioned`.
- Use **`registration_status`** only for the license workflow: `engineering`,
  `submitted`, `registered`, `granted`, `expired`, `cancelled`, `unknown`.

Partial data is allowed everywhere — a profile only requires its Circuit, a
modulation target only requires its profile and a direction. Neither endpoints
nor device/interface mappings are required at creation time. The modulation
ladder is **not** assumed to be uniform across bands.

## 4. Zabbix Usage

All endpoints are mounted under `/api/plugins/wireless-circuits/`.

Look up a profile by circuit CID:

```http
GET /api/plugins/wireless-circuits/wireless-license-profiles/?circuit_cid=MW-TX-STILES
```

Pull the flattened, Zabbix-friendly design intent for one direction (omit
`?direction=` to get both directions as a list):

```http
GET /api/plugins/wireless-circuits/wireless-license-profiles/{id}/zabbix/?direction=A_TO_Z
```

Filter modulation targets:

```http
GET /api/plugins/wireless-circuits/wireless-modulation-targets/?circuit_cid=MW-TX-STILES&direction=A_TO_Z&alarm_enabled=true
```

Authentication uses a standard NetBox API token:

```http
Authorization: Token <token>
```

### `/zabbix/` response shape

Each direction returns exactly:

```json
{
  "circuit_id": 123,
  "cid": "MW-TX-STILES-001",
  "band": "11 GHz",
  "direction": "A_TO_Z",
  "frequency_mhz": "11200.000",
  "top_modulation": "4096 QAM",
  "top_modulation_rank": 100,
  "receiver_threshold_dbm": "-74.0",
  "modulation_targets": [
    {
      "modulation": "4096 QAM",
      "modulation_rank": 100,
      "data_rate_kbps": 1000000,
      "max_power_dbm": "23.0",
      "eirp_dbm": "55.0",
      "expected_rsl_dbm": "-42.0",
      "warning_margin_db": "3.0",
      "critical_margin_db": "6.0",
      "alarm_enabled": true
    }
  ]
}
```

- `frequency_mhz` is the originating-side endpoint's `tx_frequency_mhz`
  (side `A` for `A_TO_Z`, side `Z` for `Z_TO_A`).
- `top_modulation` / `top_modulation_rank` come from the highest-ranked
  **enabled** modulation target for the direction.
- `modulation_targets` are ordered by `-modulation_rank`.
- Absent values are returned as `null`.

### Alarm logic (implement in Zabbix)

NetBox stores the expected values; Zabbix performs these comparisons:

- RX worse than `expected_rsl_dbm - warning_margin_db` → **warning**
- RX worse than `expected_rsl_dbm - critical_margin_db` → **critical**
- Live modulation rank below `top_modulation_rank` → **degradation**
- Strong RSL but low modulation → **unexpected degradation**
- TX frequency outside tolerance of licensed `tx_frequency_mhz` → **frequency mismatch**
- TX power above `maximum_power_dbm`, or far from `coordinated_power_dbm` → **power mismatch**

## CSV Import

Two importers are provided (Wireless Circuits → … → Import).

**Profile import** is keyed by Circuit CID and accepts the columns:
`cid, pcn_date, job_number, rcn_number, band, channel_plan_mhz, path_length_km,
path_length_miles, atmospheric_loss, free_space_loss, receiver_threshold,
licensee, call_sign, radio_service, station_class`. The CSV `band`,
`atmospheric_loss`, `free_space_loss`, and `receiver_threshold` columns map to
the `frequency_band`, `atmospheric_loss_db`, `free_space_loss_db`, and
`receiver_threshold_dbm` model fields.

**Modulation target import** is keyed by Circuit CID + direction and accepts:
`cid, direction, modulation, modulation_rank, data_rate_kbps, max_power_dbm,
eirp_dbm, expected_rsl_dbm, emission_designator, radio_model`. A blank
`modulation_rank` is auto-filled from the canonical rank map.

## Compatibility

- NetBox `4.5.0`
- Django `5.2`
- Python `3.10+`

## Author

[Nextlink Internet](https://nextlinkinternet.com)

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the
full text.
