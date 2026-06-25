# NetBox Wireless Circuits

A [NetBox](https://netbox.dev) 4.5 plugin for tracking licensed **microwave** and
**millimeter-wave** wireless links as native NetBox **Circuits**, with normalized
plugin models for license / PCN information, RF endpoint engineering, and
adaptive-modulation design intent.

Built and maintained by [Nextlink Internet](https://nextlinkinternet.com).

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
![NetBox 4.5](https://img.shields.io/badge/NetBox-4.5-blue)
![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue)

---

## Contents

- [Why we built this](#why-we-built-this)
- [What it does](#what-it-does)
- [Architecture](#architecture)
- [Installation](#installation)
- [Using the plugin](#using-the-plugin)
- [Tolerance and exceptions](#tolerance-and-exceptions)
- [PCN PDF import (LLM-assisted)](#pcn-pdf-import-llm-assisted) — **how to wire up the LLMs + recommended models**
- [Zabbix integration via nbxsync](#zabbix-integration-via-nbxsync)
- [REST API](#rest-api)
- [CSV import](#csv-import)
- [Development & testing](#development--testing)
- [Keeping these docs current](#keeping-these-docs-current)

---

## Why we built this

Nextlink operates a large fixed-wireless network with a substantial backbone of
**licensed point-to-point microwave and mmWave links**. Each of those links comes
with a body of engineering and regulatory truth that has to live *somewhere*: the
FCC/PCN registration, the coordinated frequency and power, the path budget, and
the adaptive-modulation ladder the radio is *expected* to ride under healthy
conditions.

Historically that information was scattered across PCN PDFs, spreadsheets, and
the heads of the RF engineers who coordinated the path. When a link degraded,
answering *"is this RSL actually a problem, or is it normal for this hop?"*
meant digging through paperwork.

This plugin makes NetBox the **system of record for the expected / licensed
values** of every wireless link, and exposes them through a clean REST API so
that **monitoring systems (we use Zabbix) can compare live radio telemetry
against the engineered design intent**. NetBox holds the truth; the monitoring
system does the math and raises the alarms.

> **Design boundary:** NetBox stores *what the link is licensed and engineered to
> do*. It does **not** evaluate live telemetry or raise alarms — that logic lives
> in Zabbix (or any consumer of the API). This keeps NetBox authoritative and
> stateless with respect to alarming.

---

## What it does

- Models each wireless link as a **native `circuits.Circuit`**, so it inherits
  NetBox status, tenancy, terminations, change logging, journaling, custom
  fields, tags, and the standard circuits UI.
- Adds a **"Wireless License" tab** to every Circuit detail page for at-a-glance
  license, endpoint, modulation, and exception data.
- Stores the **licensed / coordinated RF intent**: band, channel plan, path
  budget, receiver threshold, coordinated power, and per-direction modulation
  ladders.
- Supports **per-link exceptions** for links that legitimately cannot meet their
  PCN target, with an approval/audit trail — so the "this hop is allowed to run
  hot" decision is explicit, attributable, and time-boxed instead of tribal
  knowledge.
- Supports a **universal tolerance factor** (dB) that loosens every link's
  acceptable thresholds at once — useful for seasonal or fleet-wide allowances.
- Exposes a **Zabbix-friendly REST endpoint** that flattens all of the above
  (including effective thresholds after tolerance and exceptions) into a shape a
  monitoring template can consume directly.
- Ships **CSV import** for bulk-loading profiles and modulation ladders.

---

## Architecture

```
                          circuits.Circuit  (native NetBox)
                                   │  1:1
                                   ▼
                       WirelessLicenseProfile ──────────────┐
                          │            │                    │
                   1:N    │            │ 1:N           1:N   │
                          ▼            ▼                     ▼
          WirelessCircuitEndpoint   WirelessModulationTarget   WirelessTargetException
              (side A / side Z)      (per direction A_TO_Z /     (per-link, approved,
                                          Z_TO_A)                   time-boxed)

                       WirelessGlobalSettings  (singleton: universal tolerance)
```

### Models

| Model | Cardinality | Purpose |
|-------|-------------|---------|
| **Wireless License Profile** | one per Circuit (1:1) | License / PCN / FCC registration workflow plus path engineering (band, channel plan, path length, losses, receiver threshold). |
| **Wireless Circuit Endpoint** | two per profile (sides **A** / **Z**) | RF and site engineering for each end of the path. Optionally linked to NetBox `Site`, `Device`, and `Interface`. |
| **Wireless Modulation Target** | many per profile, per direction | The expected adaptive-modulation ladder and alarm thresholds, **per direction** (`A_TO_Z`, `Z_TO_A`). Ranked so the "top" modulation is well-defined. |
| **Wireless Target Exception** | many per profile | Records that a link is permitted not to meet its PCN target. Carries reason, approver, effective/expiry dates, an optional adjusted RSL, and an alarm-suppression flag. |
| **Wireless Global Settings** | singleton | Plugin-wide settings — primarily the **universal tolerance (dB)**. UI-editable and change-logged. |

Sides are labeled **A** and **Z** to match native circuit terminations.
Partial data is allowed everywhere: a profile only requires its Circuit, and a
modulation target only requires its profile and a direction. The modulation
ladder is **not** assumed to be uniform across bands.

---

## Installation

From the plugin source directory (the one containing `pyproject.toml`), install
into the NetBox virtual environment:

```bash
source /opt/netbox/venv/bin/activate
pip install -e .
```

Enable the plugin in NetBox `configuration.py`:

```python
PLUGINS = [
    "netbox_wireless_circuits",
]
```

Apply migrations and restart services:

```bash
cd /opt/netbox/netbox
python manage.py migrate
sudo systemctl restart netbox netbox-rq
```

### Compatibility

| Component | Version |
|-----------|---------|
| NetBox | `4.5.0` |
| Django | `5.2` |
| Python | `3.10+` |

The plugin has **no runtime dependencies** beyond NetBox itself. The Zabbix
integration is **optional**: it activates only when the
[nbxsync](https://github.com/OpensourceICTSolutions/nbxsync) plugin is installed
(`pip install netbox-wireless-circuits[zabbix]`) *and* the sync is enabled in
Global Settings. Without nbxsync, every other feature works unchanged.

---

## Using the plugin

### One-time setup

1. **Create Circuit Types** (Circuits → Circuit Types), e.g. `Licensed Microwave`,
   `Licensed Millimeter Wave`, optionally `Unlicensed Wireless Backhaul`.
2. **Create a provider / license context** (Circuits → Providers), e.g.
   `Comsearch`, `FCC/ULS`, or an internal engineering entry.

Everything the plugin adds lives under the core **Circuits** menu, in a
**Wireless Circuits** group: *Wireless License Profiles*, *Import from PCN PDF*,
*Target Exceptions*, *LLM Providers*, *LLM Settings*, *Global Settings*.
(Endpoints and modulation targets are **per-circuit** children — you manage them
from a circuit's *Wireless License* tab / profile page, not from a global list.)

### Two ways to create a wireless circuit

**A. Automatically from a PCN PDF (recommended).** Upload the coordination PDF and
let an LLM extract the fields; review and create. This builds the circuit *and*
its profile, endpoints, and modulation targets in one go — and handles PDFs that
contain multiple paths. See [PCN PDF import](#pcn-pdf-import-llm-assisted).

**B. Manually.**

1. **Create a native NetBox Circuit** with the appropriate CID and type.
2. From the Circuit's **`Wireless License`** tab, **add the wireless profile**.
3. **Add A / Z endpoints** (the tab has *Add Endpoint* buttons) with site /
   device / interface links and RF data.
4. **Add modulation targets** per direction (the profile's modulation panel has
   *Add* buttons), or bulk-load via [CSV import](#csv-import).
5. Optionally **record exceptions** and set the **global tolerance**.

### Status conventions

- Use the **native Circuit status** for operational state: `active`, `planned`,
  `offline`, `decommissioned`.
- Use the profile's **`registration_status`** only for the license workflow:
  `engineering`, `submitted`, `registered`, `granted`, `expired`, `cancelled`,
  `unknown`.

---

## Tolerance and exceptions

Two mechanisms loosen the "is this link healthy?" decision without editing every
target by hand:

### Universal tolerance (Global Settings)

A single **global tolerance (dB)** is added on top of every modulation target's
warning/critical margins. For example, a target of `-38 dBm` with a `2 dB`
tolerance treats `-40 dBm` as still acceptable. It can be toggled off
(`tolerance_enabled = false`), in which case it is treated as `0`. Edit it under
**Circuits → Wireless Circuits → Global Settings** (requires the
`change_wirelessglobalsettings` permission).

### Per-link exceptions

Some links legitimately cannot meet their PCN target (obstruction, interim
antenna, pending tower work, etc.). A **Wireless Target Exception** records that
allowance for the whole link, with:

- a required **reason**,
- the **approver** (`approved_by`, set automatically to the creating user),
- optional **effective** / **expiry** dates (the exception lapses automatically),
- an optional **adjusted RSL** to alarm against instead of the PCN target, and
- a **suppress alarms** flag to silence target-miss alarms entirely.

> **Anti-abuse:** restrict who can create or change exceptions using NetBox object
> permissions on `netbox_wireless_circuits.add_wirelesstargetexception` /
> `change_wirelesstargetexception`. Every change is captured in the NetBox change
> log, and `approved_by` records who signed off.

The `/zabbix/` endpoint surfaces the **effective** thresholds after applying both
tolerance and any active exception, so the monitoring system never has to
re-derive them.

---

## PCN PDF import (LLM-assisted)

Create wireless circuits directly from a **PCN PDF**: the plugin sends the
document to a vision-capable LLM, extracts the licensed values, and shows an
**editable preview** for you to review and correct before anything is saved. A
single PCN PDF usually contains **several path datasheets** (one per hop) — the
importer returns a `paths[]` list and creates **one circuit per path**.

> **Why an LLM — and why a *vision* model?** Coordination PDFs (e.g. Comsearch
> "Microwave Path Datasheets") are typically **image-only scans with no text
> layer** — ordinary text parsers extract nothing. Vision/OCR-capable models read
> them reliably. The plugin sends the raw PDF bytes to the provider, which does
> the OCR.

This integration is **optional and disabled by default**; none of it is required
for the rest of the plugin.

### Step 1 — install one or more provider SDKs

Install only the providers you intend to use (a provider whose SDK is missing is
simply skipped in the fallback chain). Install into the NetBox virtualenv:

```bash
source /opt/netbox/venv/bin/activate

pip install 'netbox-wireless-circuits[llm]'   # all three at once, or individually:
pip install anthropic        # Anthropic / Claude
pip install google-genai     # Google Gemini
pip install openai           # OpenAI
```

### Step 2 — provide API keys (never stored in NetBox)

Keys are read from the **environment** or from **`PLUGINS_CONFIG`** — never the
database, and never shown in the UI (the UI only reports whether a key is
*present*). Use whichever fits your deployment.

**Option A — environment variables on the NetBox service (recommended).** The
importer runs in the web process, so set the keys for the `netbox` systemd
service with a drop-in:

```bash
sudo systemctl edit netbox
```

```ini
[Service]
Environment="ANTHROPIC_API_KEY=sk-ant-..."
Environment="GEMINI_API_KEY=..."
Environment="OPENAI_API_KEY=sk-..."
```

```bash
sudo systemctl daemon-reload
sudo systemctl restart netbox
```

Set only the providers you use. The drop-in is root-readable; restrict it (or use
an `EnvironmentFile=` with tight permissions) per your security policy.

**Option B — `PLUGINS_CONFIG` in `configuration.py`** (takes precedence over the
bare environment variables):

```python
import os

PLUGINS_CONFIG = {
    "netbox_wireless_circuits": {
        "llm_api_keys": {
            "anthropic": os.environ.get("ANTHROPIC_API_KEY"),
            "gemini": os.environ.get("GEMINI_API_KEY"),
            "openai": os.environ.get("OPENAI_API_KEY"),
        },
    },
}
```

### Step 3 — define the provider fallback chain

**Wireless Circuits → LLM Providers → Add** — create one row per model in the
chain:

| Field | Meaning |
|-------|---------|
| **Rank** | Order tried; lower first (`1` = primary). |
| **Provider** | Anthropic / Google Gemini / OpenAI. |
| **Model** | Model identifier (free text — see recommendations below). |
| **Enabled** | Whether it participates in the chain. |

At extraction time the importer walks enabled rows by ascending rank and **falls
through to the next on any failure** (missing SDK, missing key, API error, or
unparseable output). Each provider's detail page shows whether its **SDK** and
**API key** are present (✓ / ✗) — without revealing the key.

### Step 4 — enable PDF import

**Wireless Circuits → LLM Settings** → turn on **PCN PDF import enabled**.
Optionally set a **prompt override** with notes specific to your PCN document
layout (appended to the extraction prompt).

### Step 5 — import

**Wireless Circuits → Import from PCN PDF**:

1. Upload the PDF and click **Extract**.
2. The review step shows shared **Provider** / **Circuit type** selectors and an
   editable `paths[]` structure (one entry per detected path). Set each path's
   **`cid`** and correct anything the model missed. *Nothing is saved yet.*
3. Click **Create** — each path becomes a circuit + wireless profile + A/Z
   endpoints + modulation targets, created **atomically**.

If extraction is disabled or every provider fails, the same screen appears with an
empty skeleton so you can enter the path(s) by hand.

### Recommended models for PDF extraction

Because the source PDFs are image scans, prefer each provider's **strongest
vision model** for accuracy on dense datasheets, with cheaper models as
fallbacks. Recommendations current as of **early 2026** — the Model field is free
text, so use whatever your account can access:

| Provider | Best accuracy | Balanced / fallback | Notes |
|----------|---------------|---------------------|-------|
| **Anthropic** | `claude-opus-4-8` | `claude-sonnet-4-6` | Excellent on dense scanned tables; strong native PDF support. |
| **Google Gemini** | `gemini-2.5-pro` | `gemini-2.5-flash` | Strong document/vision; large context window. |
| **OpenAI** | `gpt-4.1` | `gpt-4.1-mini` | Vision-capable; solid cross-vendor fallback. |

A resilient default chain (rank → model):

1. `claude-opus-4-8` (Anthropic) — primary, highest accuracy
2. `gemini-2.5-pro` (Google Gemini) — cross-vendor fallback
3. `gpt-4.1` (OpenAI) — last resort

Tips:

- For high volume / cost sensitivity, make a Sonnet / Flash / mini model the
  primary and reserve the top model as the fallback for hard documents.
- **Always review the preview.** Treat extraction as a first draft — double-check
  numeric fields (RSL, power, frequencies) on low-quality scans before creating.

### Troubleshooting

| Symptom | Cause / fix |
|---------|-------------|
| Preview is **all `null`** | Extraction is disabled (enable it in *LLM Settings*) or no provider has *both* an SDK and a key — the PDF was never read. Fix the config, or fill in the values manually. |
| "Automatic extraction failed" banner | Every provider in the chain errored (message shows why). Common causes: missing/invalid key, wrong model id, blocked network egress, rate limit. |
| A provider is silently skipped | Its SDK isn't installed, or its key isn't set. Check the provider's detail page (SDK ✓ / key ✓). |
| Extracted values look wrong | Scan quality varies. Correct them in the preview; consider a stronger primary model. |
| `SerializerNotFound` on save | Should not occur on current versions; ensure the plugin is fully upgraded and migrated. |

---

## Zabbix integration via nbxsync

NetBox is the system of record; the actual monitoring lives in Zabbix. This
plugin integrates with [**nbxsync**](https://github.com/OpensourceICTSolutions/nbxsync)
to push each link's expected values to the **receiving radio's Zabbix host** as
**user macros**, so your Zabbix template can alarm against them. The standalone
`/zabbix/` REST endpoint (below) remains available as a secondary consumer.

**How it works**

- A radio reports its own received signal level, so a direction's thresholds are
  written to the **receiver's** device: `A_TO_Z` → side Z's device, `Z_TO_A` →
  side A's. The device is taken from `WirelessCircuitEndpoint.netbox_device`.
- For each link the plugin computes the effective values (after global tolerance
  and any active exception) and writes these macros (default prefix `WL`):

  | Macro | Meaning |
  |-------|---------|
  | `{$WL.RSL.EXPECTED}` | expected RSL of the top enabled modulation |
  | `{$WL.RSL.WARN}` / `{$WL.RSL.CRIT}` | effective warning / critical RSL |
  | `{$WL.RSL.ADJUSTED}` | agreed RSL from an active exception (if set) |
  | `{$WL.MOD.TOP}` / `{$WL.MOD.TOP_RANK}` | top expected modulation + rank |
  | `{$WL.ALARM.SUPPRESS}` | `1` if an active exception suppresses alarms |
  | `{$WL.CID}` | circuit CID |

- On a multi-radio host, macros carry a **context** (the interface name), e.g.
  `{$WL.RSL.WARN:radio0}`.
- The plugin also attaches nbxsync **tags** (`wireless-circuit`, `wireless-band`)
  to classify the host for template/trigger targeting.

**Ownership** — the `{$WL.*}` macro **definitions** live in *your* Zabbix
"wireless" template (imported into nbxsync); the plugin only writes the per-device
**values** referencing them by name. Tags are owned by the plugin. If a macro
definition is missing, that macro is skipped and reported (the template hasn't
been imported yet).

**Enabling it**

1. Install nbxsync and add a ZabbixServer; import your wireless template.
2. In **Wireless Circuits → Global Settings**, turn on **Zabbix macro sync**
   (and optionally adjust the macro **prefix** / tag emission).
3. Sync happens automatically on change (Django signals). For a one-time
   backfill, use the **Sync to Zabbix** button on a profile, or:

   ```bash
   python manage.py sync_wireless_zabbix
   ```

The integration is a **soft dependency**: with nbxsync absent or the sync
disabled (the default), the plugin behaves exactly as before.

## REST API

All endpoints are mounted under `/api/plugins/wireless-circuits/`.

| Endpoint | Description |
|----------|-------------|
| `wireless-license-profiles/` | List / retrieve profiles (with nested circuit, endpoints, modulation targets). |
| `wireless-circuit-endpoints/` | A / Z endpoint RF + site data. |
| `wireless-modulation-targets/` | Per-direction modulation ladder entries. |
| `wireless-target-exceptions/` | Per-link exceptions (permission-gated). |
| `wireless-global-settings/` | Singleton global settings (permission-gated). |
| `wireless-license-profiles/{id}/zabbix/` | **Flattened, monitoring-ready** design intent. |

Authentication uses a standard NetBox API token:

```http
Authorization: Token <token>
```

### Look up by circuit CID

```http
GET /api/plugins/wireless-circuits/wireless-license-profiles/?circuit_cid=MW-TX-STILES
```

### The `/zabbix/` endpoint

Pull the flattened design intent for one direction (omit `?direction=` to get
both directions as a list):

```http
GET /api/plugins/wireless-circuits/wireless-license-profiles/{id}/zabbix/?direction=A_TO_Z
```

Each direction returns:

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
  "global_tolerance_db": "2.00",
  "exception": {
    "active": true,
    "suppress_alarms": true,
    "adjusted_rsl_dbm": null,
    "reason": "awaiting tower work",
    "effective_date": null,
    "expiry_date": null
  },
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
      "alarm_enabled": true,
      "effective_warning_rsl_dbm": "-47.000",
      "effective_critical_rsl_dbm": "-50.000"
    }
  ]
}
```

- `frequency_mhz` is the originating-side endpoint's `tx_frequency_mhz`
  (side `A` for `A_TO_Z`, side `Z` for `Z_TO_A`).
- `top_modulation` / `top_modulation_rank` come from the highest-ranked
  **enabled** modulation target for the direction.
- `modulation_targets` are ordered by `-modulation_rank`.
- `global_tolerance_db` is the effective tolerance (`0` when disabled).
- `exception` is `null` when no exception is active for the link.
- `effective_warning_rsl_dbm` = `expected_rsl_dbm − (warning_margin_db + tolerance)`;
  `effective_critical_rsl_dbm` uses the critical margin. These are the thresholds
  the monitoring system should alarm against.
- Absent values are returned as `null`.

### Alarm logic (implement in the monitoring system)

NetBox stores the expected values; the consumer performs the comparisons:

- RX worse than `effective_warning_rsl_dbm` → **warning**
- RX worse than `effective_critical_rsl_dbm` → **critical**
- Live modulation rank below `top_modulation_rank` → **degradation**
- Strong RSL but low modulation → **unexpected degradation**
- TX frequency outside tolerance of licensed `tx_frequency_mhz` → **frequency mismatch**
- TX power above `maximum_power_dbm`, or far from `coordinated_power_dbm` → **power mismatch**
- If `exception.active` and `exception.suppress_alarms` → **suppress RSL target-miss alarms** for the link.

---

## CSV import

Two importers are available under **Wireless Circuits → … → Import**.

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

---

## Development & testing

Run the plugin test suite against a NetBox checkout that has the plugin
installed and enabled:

```bash
cd /opt/netbox/netbox
python manage.py test netbox_wireless_circuits --keepdb
```

The suite covers the models, filtersets, the singleton settings and exception
behavior, and the `/zabbix/` API contract (including tolerance and exception
surfacing).

Migrations are generated, not hand-written:

```bash
python manage.py makemigrations netbox_wireless_circuits
```

---

## Roadmap

- Richer field-by-field preview UI for the PCN importer (currently the
  review/mapping step is an editable structured JSON of the extracted values).
- Auto-detect and pre-fill the per-path CID from the document.

---

## Keeping these docs current

This README is kept in sync with the code by a dedicated **Claude Code subagent**
checked into the repo at [`.claude/agents/docs-maintainer.md`](.claude/agents/docs-maintainer.md).
It reads the models, choices, settings, navigation, API, and the LLM/PCN modules,
then reconciles the relevant README sections — the model/choice tables, settings
and menu items, API endpoints, Zabbix macro list, the PCN import steps, and the
**recommended-models** table (refreshing the "current as of" date).

After any feature change, run it from Claude Code in this repo:

```
> Use the docs-maintainer agent to update the README for my recent changes.
```

It documents only what exists in the code (no speculation), preserves the
structure and voice, and reports a summary of what it changed. It edits docs
only — never application code.

## Contributing

Issues and pull requests are welcome. Please run the test suite before opening a
PR and keep migrations generated (not hand-edited). If your change affects usage,
settings, the menu, the API, or the LLM/PCN behavior, run the **docs-maintainer**
agent (above) so the README stays accurate.

## License

Licensed under the **Apache License, Version 2.0**. See [LICENSE](LICENSE) for
the full text.

Copyright © 2026 [Nextlink Internet](https://nextlinkinternet.com).
