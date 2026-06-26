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
- [Bulk import (Comsearch & other coordinator CSV exports)](#bulk-import-comsearch--other-coordinator-csv-exports)
- [CSV import (single-model, by CID)](#csv-import-single-model-by-cid)
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
- Ships a **source-aware bulk CSV importer** (Comsearch today) that builds whole
  links from a coordinator export, de-duplicates on re-upload, and reports — rather
  than overwrites — changes to links that already exist; plus simpler CSV importers
  for bulk-loading profiles and modulation ladders by CID.
- **Auto-tags each circuit** with its N+0 radio configuration (e.g.
  `link_type: 2+0`) so links are filterable by type in the core Circuits list.
- Maintains a reusable **antenna catalog ("warehouse")** of make/models that
  endpoints can reference; the PCN importer auto-populates it as it sees antennas.

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

Everything the plugin adds lives in its own **Wireless Circuits** menu in the
plugins navigation section, organized into four groups:

- **Circuits** — *Wireless License Profiles*, *Import* (a single entry that opens
  the import hub — choose PCN-PDF or Comsearch/CSV bulk import there).
- **Catalog** — *Antennas*, *Target Exceptions*, *Band Tolerances*.
- **LLM Import** — *LLM Providers*, *Available LLM Models*, *LLM Settings*.
- **Settings** — *Global Settings*.

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
   device / interface links and RF data. Each endpoint can also reference a
   reusable **Antenna (catalog)** entry (see [Antenna catalog](#antenna-catalog)).
4. **Add modulation targets** per direction (the profile's modulation panel has
   *Add* buttons), or bulk-load via [CSV import](#csv-import).
5. Optionally **record exceptions** and set the **global tolerance**.

### Automatic link-type tag

Every wireless circuit is automatically given a **NetBox tag** reflecting its
profile's **N+0 radio configuration** (carrier aggregation), so links are
filterable in the **core Circuits list** by their link type. The tag is applied
to the **Circuit** whenever a profile is created (including via PCN import) and
kept in sync if `radio_configuration` later changes — the stale tag is removed
and the new one applied.

The tag name comes from a template in **Wireless Circuits → Global Settings**
where `{config}` is replaced by the N+0 value:

- `link_type_tag_enabled` — turn the auto-tag on or off (default **on**).
- `link_type_tag_template` — the tag-name template (default
  `link_type: {config}`, producing e.g. `link_type: 2+0`). Set it to `{config}`
  for the value only (`2+0`), or `MW-{config}` for a prefix (`MW-2+0`).

A profile with no `radio_configuration` gets no link-type tag.

### Status conventions

A wireless link has **two independent status axes** — keep them distinct:

- **Operational state** — the **native Circuit status** (`active`, `planned`,
  `offline`, `decommissioned`). Whether the link is in service.
- **FCC license status** — the regulatory state, using coordinator (FCC/Comsearch)
  vocabulary: `Licensed`, `Applied`, `Proposed`, `Replaced`, `Expired or
  Terminated`, `Transitional`, `Questionable`, `Protection Declined`, `Temporary`,
  `Unknown`.

License status is tracked **per endpoint** (each end of the path holds its own
FCC license), on `WirelessCircuitEndpoint.license_status`. The profile shows a
single **rolled-up headline badge** (`registration_status`): when the two ends
match it's that value; when they differ the most attention-worthy status wins and
the UI flags it **Mixed**.

#### License expiration / renewal tracking

Each endpoint carries its own `license_application_date`, `license_effective_date`,
and `license_expiration_date` (plus `license_basis` — Primary/Secondary — and a
`conditional_authorization` flag). The profile surfaces the **earliest** of the two
ends' expirations as `license_expiration`, with derived `license_expiring_soon`
(within 90 days) and `license_expired` indicators shown on the profile, the
circuit's Wireless tab, and the profile list. Filter links due for renewal with
`?license_expires_before=YYYY-MM-DD`. All of these fields are exposed in the
[REST API](#rest-api).

---

## Tolerance and exceptions

Two mechanisms loosen the "is this link healthy?" decision without editing every
target by hand:

### Tolerance — acceptable dB off target (global, optionally per band)

How many dB a link may run off its PCN target before alarming is a **global
rule**, with optional **per-band** overrides:

- **Default tolerance** — a single dB value in **Wireless Circuits → Global
  Settings** (`global_tolerance_db`), applied to every band that has no specific
  rule. The master `tolerance_enabled` switch disables *all* allowance when off.
- **Per-band rules** — under **Wireless Circuits → Band Tolerances**, set the
  allowed dB per license band (e.g. *11 GHz → 1.5 dB*). Change it later, or set
  **0** to require that band to meet target exactly (no allowance). A disabled
  band rule falls back to the default. Fresh installs are **seeded with defaults**
  — 6 GHz → 1 dB, 11 GHz → 1.5 dB, 18 GHz → 1.5 dB, 70/80 GHz → 2 dB — which you
  can edit or delete.

The effective tolerance for a link resolves as **band rule (if enabled) →
default → 0**, and is added on top of each modulation target's warning/critical
margins. Example: a `-38 dBm` target with a `2 dB` 11 GHz rule treats `-40 dBm`
as still acceptable. (This is distinct from a **per-link exception** below, which
is an explicit, approved one-off for a specific link.)

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

**Option A — the `configure_llm` wizard (recommended, one command).** A management
command walks you through the whole setup: pick a provider, choose a model, set a
rank, and paste the key. The key is written to the systemd environment file (it is
**never** stored in NetBox's database); the provider row in the fallback chain
(Step 3) is created/updated for you; and PCN-PDF import (Step 4) and a service
restart are offered at the end. Run it with `sudo` so it can write the root-owned
env file and restart the service:

```bash
sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py configure_llm
```

What it does, interactively:

1. **Lists the providers** (Anthropic / Google Gemini / OpenAI, with whether each
   SDK is installed) and lets you pick one by number.
2. Prompts for the **model identifier** (with a sensible default per provider).
3. Prompts for the **rank** (`1` = tried first).
4. Prompts **silently** (no echo) for the **API key**, then writes it to the env
   file (default `/etc/netbox-wireless-llm.env`, mode `600`) — the same path the
   `netbox.service.d/llm.conf` drop-in loads via `EnvironmentFile=`. Leaving the
   prompt blank **keeps the existing key**, and other providers' keys already in
   the file are **preserved** (it merges, it does not overwrite the file).
5. Creates or updates the matching **LLM Providers** row in the fallback chain.
6. Offers to **enable PCN-PDF import**.
7. Offers to **restart NetBox** (`systemctl restart netbox netbox-rq`) so the key
   takes effect.

For automation, the same command takes non-interactive flags:
`--provider`, `--model`, `--rank`, `--key-stdin` (read the key from stdin so it
stays out of the process arguments), `--env-file`, `--enable-import` /
`--no-enable-import`, `--restart` / `--no-restart`, and `--no-input` (fail instead
of prompting). For example:

```bash
printf '%s' "$ANTHROPIC_API_KEY" | sudo /opt/netbox/venv/bin/python \
  /opt/netbox/netbox/manage.py configure_llm \
  --provider anthropic --model claude-haiku-4-5 --rank 1 \
  --key-stdin --enable-import --restart --no-input
```

If you prefer to wire the key in by hand, the two options below remain fully
supported.

**Option B — environment variables on the NetBox service.** The
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

**Option C — `PLUGINS_CONFIG` in `configuration.py`** (takes precedence over the
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

> If you used the `configure_llm` wizard in Step 2 it already created/updated a row
> for you; use this section to add **additional** models to the chain.

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

**Wireless Circuits → Import → Open PDF importer**:

1. Upload the PDF and click **Extract**.
2. The review step shows shared **Provider** / **Circuit type** selectors and an
   editable `paths[]` structure (one entry per detected path). Set each path's
   **`cid`** and correct anything the model missed. *Nothing is saved yet.*

   This step also shows a card with a **per-side mapping row** for each side
   (A/Z) of every extracted path, offering **Site**, **Radio device**, and
   **Interface** dropdowns. The device list is filtered by the chosen Site and
   the interface list by the chosen device. These rows are built dynamically once
   extraction reveals how many paths there are. Mapping is **optional**: a side's
   Site is **pre-selected** when its extracted `pcn_site_name` exactly matches
   (case-insensitive) an existing NetBox Site name, otherwise it's left blank.
   Any chosen object is written onto the plugin's
   `WirelessCircuitEndpoint.netbox_site` / `netbox_device` / `netbox_interface`
   (the RF record), and assigning a **Site** additionally creates or updates that
   circuit's **native NetBox `CircuitTermination`** for that side (A or Z),
   terminated to the Site — so the core Circuit's Termination A/Z is populated,
   not just the RF record. This is idempotent: one termination per side, reused on
   re-import. Leaving a side's fields blank leaves those links **null** and creates
   **no** termination for that side. You can always set or change them later on
   each circuit/endpoint.
3. Click **Create** — each path becomes a circuit + wireless profile + A/Z
   endpoints + modulation targets (with any chosen sites applied), created
   **atomically**.

If extraction is disabled or every provider fails, the same screen appears with an
empty skeleton so you can enter the path(s) by hand.

#### The source PCN PDF is retained

The PDF you upload in Step 1 is stashed for the wizard and a **copy is attached to
every profile it creates** (`pcn_document`). Because one PDF can yield several
circuits, each resulting profile gets its own copy. The file is then available:

- as a **"Download PCN PDF"** link on the circuit's **Wireless License** tab, and
- as a file URL in the profile's `pcn_document` field in the [REST API](#rest-api).

#### Deleting wizard-imported circuits and profiles

Because the wizard *creates* the circuit, each profile it produces is flagged
**`created_via_import = True`** (visible on the profile and in the
[REST API](#rest-api)). This changes delete behavior:

- **Deleting a wizard-imported profile also deletes its underlying NetBox
  Circuit** (and that circuit's terminations), since the wizard created the
  circuit in the first place.
- **A profile attached to a pre-existing circuit via the manual "Add Wireless
  License Profile" form has `created_via_import = False`**, so deleting it
  removes only the profile and leaves the circuit intact.
- **Deleting the Circuit directly always cascades to the profile** (and its
  endpoints, modulation targets, and terminations) as before; a guard prevents
  the profile signal from trying to re-delete the circuit in that case.
- This applies to **single and bulk deletes**.

#### Carrier aggregation (N+0)

The extractor also reads the link's **carrier configuration**:

- **`carrier_count`** — the number of distinct bonded RF carriers / channels on
  the link, counted from the document's *TRANSMIT FREQUENCIES* / channel-plan
  section (each go/return frequency **pair** is one carrier; a single-channel
  link is `1`).
- **`radio_configuration`** — the N+0 aggregation notation (`1+0`, `2+0`, `4+0`).
  If the document states it, the model returns it; otherwise the importer
  **derives `{carrier_count}+0`** at create time (assuming an *unprotected*
  configuration). Edit the profile afterward if the link is actually N+1.

Both fields are editable on the profile, shown on the profile detail page (a
configuration badge plus the carrier count) and in the profile list table, and
exposed in the [REST API](#rest-api). The profile detail also shows the
**aggregate expected throughput** per direction — the top alarm-enabled
modulation's per-carrier data rate × `carrier_count`.

#### Antenna catalog auto-population

The extractor also reads each side's antenna details (`antenna_code`,
`antenna_manufacturer`, `antenna_model`, `antenna_diameter_ft`,
`antenna_gain_dbi`, `antenna_beamwidth_deg`). On create, the importer
**get-or-creates** a catalog entry keyed by **manufacturer + antenna code** and
links it to the endpoint's `antenna` field. The first time a code is seen it
stubs out a catalog entry from the extracted values; if the entry already exists
it is **left untouched** (never overwritten), so operator-enriched make/model
details survive re-imports. See [Antenna catalog](#antenna-catalog) below.

### Antenna catalog

The **antenna catalog** ("warehouse") is a reusable list of antenna make/models
(**Wireless Circuits → Antennas**), each carrying manufacturer, antenna code,
model, diameter (ft / m), gain (dBi), beamwidth, polarization, frequency range,
and notes. Entries are **unique on (manufacturer, antenna code)**.

- Each **endpoint** can reference one catalog entry via its **Antenna (catalog)**
  picker on the endpoint edit form. This is **additive**: the per-endpoint
  free-text `antenna_*` fields remain for the path-specific record, while the
  catalog holds the shared spec.
- The PCN importer **auto-creates and links** a catalog entry the first time it
  sees an antenna (see [Antenna catalog auto-population](#antenna-catalog-auto-population)),
  keyed by manufacturer + antenna code and never overwriting an existing entry.
- Operators add or refine make/model details in the catalog over time; CRUD is
  available from the *Antennas* list and via the
  [REST API](#rest-api) at `wireless-antennas/`.

### Recommended models for PDF extraction

The source PDFs are **image scans with dense numeric tables**, so use a
**vision/OCR-capable** model — and be aware the cheapest tiers can misread small
digits. Recommendations current as of **early 2026**; the Model field is free
text, so use whatever your account can access (see *Discover available models*
below to fetch live IDs).

| Provider | Best accuracy | Balanced | Cheapest | Notes |
|----------|---------------|----------|----------|-------|
| **Anthropic** | `claude-opus-4-8` | `claude-sonnet-4-6` | `claude-haiku-4-5` | Strong on dense scanned tables. Approx. price (in/out per 1M tok): Opus 4.8 $5/$25, Sonnet 4.6 $3/$15, Haiku 4.5 $1/$5. |
| **Google Gemini** | `gemini-2.5-pro` | `gemini-2.5-flash` | `gemini-2.5-flash-lite` | Flash is often the best **value** for document extraction (cheap, fast, large context). Verify current pricing with Google. |
| **OpenAI** | `gpt-4.1` | `gpt-4o` | `gpt-4.1-mini` | Vision-capable; solid cross-vendor fallback. Verify current pricing with OpenAI. |

**Cheap & efficient chain** (rank → model) — lowest cost first, accuracy fallback second:

1. `gemini-2.5-flash` (or `claude-haiku-4-5` to stay single-vendor) — cheap primary
2. `claude-sonnet-4-6` — accuracy fallback when the cheap model returns garbled numbers
3. `gpt-4.1-mini` — cross-vendor backstop

**Max-accuracy chain** (when correctness matters more than cost):

1. `claude-opus-4-8` → 2. `gemini-2.5-pro` → 3. `gpt-4.1`

Tips:

- **Always review the preview.** Treat extraction as a first draft — double-check
  numeric fields (RSL, power, frequencies) on low-quality scans before creating.
- Validate your chosen primary on a representative PDF; if the cheap model
  misreads digits, promote a stronger model to primary.

### Discover available models

**Wireless Circuits → Available LLM Models** queries each provider whose **SDK is
installed and key is configured** and lists the model IDs currently available to
your account (Anthropic is filtered toward chat/vision models; OpenAI is trimmed
to the `gpt`/`o*` families). Copy an ID straight into an **LLM Providers** row —
this keeps the free-text Model field honest against what your account can
actually call. Providers without an SDK or key are shown but not queried.

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
  | `{$WL.CARRIERS}` | number of bonded RF carriers (N+0); always emitted, defaults to `1` |
  | `{$WL.CONFIG}` | radio configuration notation (e.g. `2+0`); emitted only when set |
  | `{$WL.THROUGHPUT.EXPECTED_KBPS}` | aggregate expected throughput (top enabled modulation's per-carrier rate × carriers); emitted only when a per-carrier data rate is set |
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
| `wireless-antennas/` | Reusable antenna catalog ("warehouse") entries. |
| `wireless-target-exceptions/` | Per-link exceptions (permission-gated). |
| `wireless-band-tolerances/` | Per-band tolerance rules. |
| `wireless-global-settings/` | Singleton global settings (permission-gated). |
| `wireless-llm-settings/` | Singleton PCN importer settings. |
| `wireless-llm-providers/` | LLM fallback-chain entries. |
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
  "carrier_count": 2,
  "radio_configuration": "2+0",
  "aggregate_data_rate_kbps": 786432,
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

## Bulk import (Comsearch & other coordinator CSV exports)

**Wireless Circuits → Import** is a single hub that lets you pick an import
**type** and, for CSV, a **data source**:

- **PCN PDF** — the LLM-assisted, review-then-create wizard for one coordination
  document (see [PCN PDF import](#pcn-pdf-import-llm-assisted)).
- **CSV** — bulk-load a coordinator's full export. The importer is **source-aware**:
  each data source (e.g. **Comsearch**) has its own column layout and its own
  stable per-link key. Adding another coordinator later is a new adapter, not a
  rewrite of the importer.

### How the Comsearch CSV import works

Comsearch's microwave-links export carries **one link per (wide) row**; side `1`
maps to endpoint **A** and side `2` to endpoint **Z**. The importer:

- **Normalizes** the export's formats to the plugin's models: band labels
  (`11 GHz (10700-11700 MHz) US` → `11 GHz`, `6.1`/`6.7 GHz` → `6 GHz`),
  modulations (incl. `OFDM 1024QA` → `1024 QAM`, `4 QAM` → `QPSK`),
  DMS coordinates (`33 10 52.86 N` → signed decimal degrees), and Excel-escaped
  RCNs (`="260623C5"` → `260623C5`). Carrier count is derived from the number of
  populated transmit-frequency pairs (→ `radio_configuration`).
- Builds, per row, a **circuit + license profile + A/Z endpoints + per-direction
  modulation targets**, and auto-populates the [antenna catalog](#antenna-catalog).
- Maps each end's **FCC license status** (`status1`/`status2` → per-endpoint
  `license_status`, rolled up to the link badge), **license expiration** /
  effective / application dates, license basis, and conditional-authorization
  flag — see [Status conventions](#status-conventions).

#### De-duplication on re-upload

Each link gets a stable **import key** = unordered **site pair + band + RCN +
center frequency** (verified unique across the full export), stored on the profile
as `import_source` (`comsearch`) + `import_key`. On every import:

- a link whose key is **not yet present** is **created**;
- a link that **already exists** is **diffed and reported — not modified**. The
  result lists exactly which fields changed for each existing link, so you can
  review what Comsearch updated without overwriting any operator edits (NetBox
  site/device/interface links, tags, exceptions, antenna-catalog enrichment are
  never touched).

So re-uploading the same — or an updated — export **never creates duplicates**.

#### It runs as a background job

A full export is thousands of links, so the upload is dispatched to a **background
job** (netbox-rq) rather than blocking the request. After you click **Queue
import** the page redirects to the job, whose result shows the
**created / changed / unchanged / errors** summary and the per-link change report.

For the initial large load or scheduled re-syncs, the same engine is available on
the command line:

```bash
python manage.py import_wireless_csv --source comsearch \
    --provider "Comsearch" --type "Licensed Microwave" mwlinks-export.csv
```

`--source`, `--provider`, and `--type` are required; `--status` is optional and
sets the new circuits' status (default `active`). The command prints the same
**created / changed / unchanged / errors** summary as the web job, with a line per
changed link.

`import_source`, `import_key`, and `import_link_id` are exposed on the profile in
the [REST API](#rest-api).

## CSV import (single-model, by CID)

Two row-per-object importers are also available under
**Wireless Circuits → … → Import** (the column-header `Import` buttons), for
loading flat data onto **existing** circuits keyed by CID.

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
