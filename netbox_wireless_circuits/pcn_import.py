"""
Map an extracted (or manually-entered) PCN data structure onto plugin models.

The extraction JSON (from :mod:`netbox_wireless_circuits.llm`, or hand-edited in
the preview step) is shaped as::

    {"profile": {...}, "endpoints": [{...}], "modulation_targets": [{...}]}

Unknown keys are ignored and empty values dropped, so a partial / imperfect LLM
result still imports cleanly and the operator can fix the rest in the preview.
"""
from django.db import transaction

from .models import (
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessModulationTarget,
)

PROFILE_FIELDS = {
    "pcn_number", "rcn_number", "job_number", "licensee", "call_sign",
    "radio_service", "station_class", "frequency_band", "channel_plan_mhz",
    "path_length_km", "path_length_miles", "atmospheric_loss_db",
    "free_space_loss_db", "receiver_threshold_dbm",
    "carrier_count", "radio_configuration",
}
ENDPOINT_FIELDS = {
    "side", "pcn_site_name", "county_state", "latitude", "longitude",
    "tx_frequency_mhz", "antenna_model", "antenna_gain_dbi", "path_azimuth_deg",
    "radio_model", "polarization",
}
TARGET_FIELDS = {
    "direction", "modulation", "data_rate_kbps", "max_power_dbm", "eirp_dbm",
    "expected_rsl_dbm", "emission_designator", "radio_model",
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


@transaction.atomic
def create_circuit_and_profile(cid, provider, circuit_type, data, status="active"):
    """
    Create a NEW circuit and its wireless profile (+ endpoints + targets) from a
    single path's PCN data, in one atomic step. Returns ``(circuit, profile)``.
    """
    from circuits.models import Circuit

    circuit = Circuit.objects.create(
        cid=cid, provider=provider, type=circuit_type, status=status,
    )
    profile = create_from_extraction(circuit, data)
    return circuit, profile


@transaction.atomic
def create_paths(provider, circuit_type, data, status="active"):
    """
    Create a circuit + profile for EACH path in ``data['paths']`` (a PCN PDF may
    hold several). All-or-nothing. Returns a list of ``(circuit, profile)``.
    Each path must carry a non-empty ``cid``.
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
            create_circuit_and_profile(cid, provider, circuit_type, path, status)
        )
    return results


@transaction.atomic
def create_from_extraction(circuit, data):
    """
    Create a profile (+ endpoints + modulation targets) on ``circuit`` from a
    PCN data dict. Atomic: any model validation error rolls the whole thing back.
    Returns the created :class:`WirelessLicenseProfile`.
    """
    prof_fields = _filtered(data.get("profile"), PROFILE_FIELDS)
    # Derive the N+0 label from the carrier count when the document didn't state
    # one explicitly (assumes unprotected; edit on the profile if it's N+1).
    if prof_fields.get("carrier_count") and not prof_fields.get("radio_configuration"):
        try:
            prof_fields["radio_configuration"] = f"{int(prof_fields['carrier_count'])}+0"
        except (TypeError, ValueError):
            pass
    # created_via_import marks the circuit as wizard-created so deleting the
    # profile later also removes the circuit it created (see signals).
    profile = WirelessLicenseProfile.objects.create(
        circuit=circuit, created_via_import=True, **prof_fields
    )
    for ep in (data.get("endpoints") or []):
        fields = _filtered(ep, ENDPOINT_FIELDS)
        # netbox_site is a Site instance injected by the wizard (a per-side
        # dropdown), not part of the JSON whitelist; carry it through if present.
        site = (ep or {}).get("netbox_site")
        if site:
            fields["netbox_site"] = site
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
    return profile
