"""
Map an extracted (or manually-entered) PCN data structure onto plugin models.

The extraction JSON (from :mod:`netbox_wireless_circuits.llm`, or hand-edited in
the preview step) is shaped as::

    {"profile": {...}, "endpoints": [{...}], "modulation_targets": [{...}]}

Unknown keys are ignored and empty values dropped, so a partial / imperfect LLM
result still imports cleanly and the operator can fix the rest in the preview.
"""
import logging

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils.text import slugify

from .models import (
    WirelessAntenna,
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessModulationTarget,
)

logger = logging.getLogger("netbox_wireless_circuits")

PROFILE_FIELDS = {
    "pcn_date", "pcn_number", "rcn_number", "job_number",
    "registration_status", "registration_date", "registration_completion_date",
    "licensee", "call_sign", "radio_service", "station_class",
    "frequency_band", "channel_plan_mhz",
    "path_length_km", "path_length_miles", "atmospheric_loss_db",
    "free_space_loss_db", "receiver_threshold_dbm",
    "carrier_count", "radio_configuration", "source_document", "notes",
}
ENDPOINT_FIELDS = {
    "side", "pcn_site_name", "county_state", "latitude", "longitude",
    "ground_elevation_m", "ground_elevation_ft", "asr_number",
    "structure_height_agl_m", "structure_height_agl_ft", "path_azimuth_deg",
    "license_status", "license_basis", "conditional_authorization",
    "license_application_date", "license_effective_date", "license_expiration_date",
    "antenna_code", "antenna_manufacturer", "antenna_model",
    "antenna_diameter_ft", "antenna_gain_dbi", "antenna_beamwidth_deg",
    "antenna_tilt_deg", "centerline_agl_m", "centerline_agl_ft",
    "transmit_mode", "radio_code", "radio_manufacturer", "radio_model",
    "radio_description", "stability_percent",
    "nominal_power_dbm", "nominal_rsl_dbm", "coordinated_power_dbm",
    "coordinated_rsl_dbm", "maximum_power_dbm", "maximum_rsl_dbm",
    "fixed_loss_common_db", "fixed_loss_tx_db", "fixed_loss_rx_db",
    "tx_frequency_mhz", "polarization",
}
TARGET_FIELDS = {
    "direction", "modulation", "modulation_rank", "data_rate_kbps",
    "max_power_dbm", "eirp_dbm", "expected_rsl_dbm",
    "min_acceptable_rsl_dbm", "max_acceptable_rsl_dbm",
    "emission_designator", "radio_model",
}

# Empty template for one path; a PDF may contain several.
PATH_SKELETON = {
    "cid": None,
    "profile": {k: None for k in sorted(PROFILE_FIELDS)},
    "endpoints": [
        {k: ("A" if k == "side" else None) for k in sorted(ENDPOINT_FIELDS)},
        {k: ("Z" if k == "side" else None) for k in sorted(ENDPOINT_FIELDS)},
    ],
    "modulation_targets": [
        {k: None for k in sorted(TARGET_FIELDS)},
    ],
}

# Top-level skeleton for fully-manual entry when extraction is off or fails.
SKELETON = {"paths": [PATH_SKELETON]}


def _filtered(d, allowed):
    return {
        k: v for k, v in (d or {}).items()
        if k in allowed and v not in (None, "")
    }


def resolve_antenna(ep):
    """
    Get-or-create the catalog antenna for an endpoint dict, keyed by
    (manufacturer, antenna_code). Auto-creates a stub from the extracted antenna
    fields the first time a code is seen; never overwrites an existing entry (the
    operator may have enriched it). Returns the WirelessAntenna or None when no
    antenna code was extracted.
    """
    code = (ep.get("antenna_code") or "").strip()
    if not code:
        return None
    manufacturer = (ep.get("antenna_manufacturer") or "").strip()
    defaults = {}
    for src, dst in (
        ("antenna_model", "model"),
        ("antenna_diameter_ft", "diameter_ft"),
        ("antenna_gain_dbi", "gain_dbi"),
        ("antenna_beamwidth_deg", "beamwidth_deg"),
    ):
        value = ep.get(src)
        if value not in (None, ""):
            defaults[dst] = value
    antenna, _ = WirelessAntenna.objects.get_or_create(
        manufacturer=manufacturer, antenna_code=code, defaults=defaults
    )
    return antenna


def ensure_circuit_termination(circuit, term_side, site):
    """
    Create or update the native NetBox CircuitTermination for one side of the
    circuit, terminated to ``site``. Idempotent (one termination per side). This
    is what populates the core Circuit's Termination A/Z; the wireless endpoint's
    ``netbox_site`` only links the plugin's RF record.
    """
    from circuits.models import CircuitTermination

    if term_side not in ("A", "Z") or site is None:
        return None
    ct = CircuitTermination.objects.filter(
        circuit=circuit, term_side=term_side
    ).first()
    if ct is None:
        ct = CircuitTermination(circuit=circuit, term_side=term_side)
    # ``termination`` is the scoped GFK (Site/Location/Region/...); assigning a
    # Site and saving denormalizes _site/_region/etc.
    ct.termination = site
    ct.save()
    return ct


def _attach_pcn_document(profile, pdf_bytes, pdf_name):
    """
    Save the source PCN PDF onto the profile's pcn_document field. Best-effort:
    a storage failure (permissions, read-only/full media, etc.) is logged but
    never aborts the import — the circuit + profile are kept regardless, the PDF
    just isn't attached. The file is written via Django's storage, which creates
    the MEDIA_ROOT subdirectories on first use.
    """
    if not pdf_bytes:
        return
    base = slugify(profile.circuit.cid) or "pcn"
    name = f"{base}.pdf"
    try:
        profile.pcn_document.save(name, ContentFile(pdf_bytes), save=True)
    except Exception as exc:  # storage/permissions/disk — don't fail the import
        logger.warning(
            "netbox_wireless_circuits: could not attach PCN PDF to %s: %s",
            profile.circuit.cid, exc,
        )


@transaction.atomic
def create_circuit_and_profile(cid, provider, circuit_type, data, status="active",
                               pdf_bytes=None, pdf_name=None, extra_profile=None):
    """
    Create a NEW circuit and its wireless profile (+ endpoints + targets) from a
    single path's PCN data, in one atomic step. Returns ``(circuit, profile)``.
    ``pdf_bytes`` (the source PCN PDF) is retained on the profile if provided.
    ``extra_profile`` is a dict of additional profile fields to stamp directly
    (e.g. ``import_source`` / ``import_key`` from a bulk CSV import).
    """
    from circuits.models import Circuit

    circuit = Circuit.objects.create(
        cid=cid, provider=provider, type=circuit_type, status=status,
    )
    profile = create_from_extraction(
        circuit, data, pdf_bytes=pdf_bytes, pdf_name=pdf_name,
        extra_profile=extra_profile,
    )
    return circuit, profile


@transaction.atomic
def create_paths(provider, circuit_type, data, status="active",
                 pdf_bytes=None, pdf_name=None):
    """
    Create a circuit + profile for EACH path in ``data['paths']`` (a PCN PDF may
    hold several). All-or-nothing. Returns a list of ``(circuit, profile)``.
    Each path must carry a non-empty ``cid``. The source PCN PDF (``pdf_bytes``)
    is attached to every created profile.
    """
    paths = data.get("paths") or []
    if not paths:
        raise ValueError("No paths to import (expected a non-empty 'paths' list).")
    results = []
    for idx, path in enumerate(paths, start=1):
        cid = (path.get("cid") or "").strip()
        if not cid:
            raise ValueError(f"Path #{idx} is missing a 'cid'.")
        results.append(
            create_circuit_and_profile(
                cid, provider, circuit_type, path, status,
                pdf_bytes=pdf_bytes, pdf_name=pdf_name,
            )
        )
    return results


@transaction.atomic
def create_from_extraction(circuit, data, pdf_bytes=None, pdf_name=None,
                           extra_profile=None):
    """
    Create a profile (+ endpoints + modulation targets) on ``circuit`` from a
    PCN data dict. Atomic: any model validation error rolls the whole thing back.
    Returns the created :class:`WirelessLicenseProfile`. ``extra_profile`` stamps
    additional profile fields (e.g. import provenance) outside the JSON whitelist.
    """
    prof_fields = _filtered(data.get("profile"), PROFILE_FIELDS)
    # Derive the N+0 label from the carrier count when the document didn't state
    # one explicitly (assumes unprotected; edit on the profile if it's N+1).
    if prof_fields.get("carrier_count") and not prof_fields.get("radio_configuration"):
        try:
            prof_fields["radio_configuration"] = f"{int(prof_fields['carrier_count'])}+0"
        except (TypeError, ValueError):
            pass
    if extra_profile:
        prof_fields.update(extra_profile)
    # created_via_import marks the circuit as wizard-created so deleting the
    # profile later also removes the circuit it created (see signals).
    profile = WirelessLicenseProfile.objects.create(
        circuit=circuit, created_via_import=True, **prof_fields
    )
    for ep in (data.get("endpoints") or []):
        ep = ep or {}
        fields = _filtered(ep, ENDPOINT_FIELDS)
        # netbox_site/device/interface are model instances injected by the wizard
        # (per-side dropdowns), not part of the JSON whitelist; carry through.
        for key in ("netbox_site", "netbox_device", "netbox_interface"):
            value = ep.get(key)
            if value:
                fields[key] = value
        # Auto-create / link the reusable catalog antenna from the extracted code.
        antenna = resolve_antenna(ep)
        if antenna:
            fields["antenna"] = antenna
        site = ep.get("netbox_site")
        side = fields.get("side")
        if side:
            WirelessCircuitEndpoint.objects.create(
                wireless_license_profile=profile, **fields
            )
            # Also populate the native circuit's A/Z termination so the core
            # Circuit reflects where each end lands, not just the RF record.
            if site:
                ensure_circuit_termination(circuit, side, site)
    for target in (data.get("modulation_targets") or []):
        fields = _filtered(target, TARGET_FIELDS)
        if fields.get("direction") and fields.get("modulation"):
            WirelessModulationTarget.objects.create(
                wireless_license_profile=profile, **fields
            )
    # Attach the PDF last (best-effort) so a storage hiccup can't strand the
    # DB work, and nothing is written for a path that errored earlier.
    _attach_pcn_document(profile, pdf_bytes, pdf_name)
    return profile
