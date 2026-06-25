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

# Empty template for fully-manual entry when extraction is off or fails.
SKELETON = {
    "profile": {k: None for k in sorted(PROFILE_FIELDS)},
    "endpoints": [
        {k: ("A" if k == "side" else None) for k in sorted(ENDPOINT_FIELDS)},
        {k: ("Z" if k == "side" else None) for k in sorted(ENDPOINT_FIELDS)},
    ],
    "modulation_targets": [
        {k: None for k in sorted(TARGET_FIELDS)},
    ],
}


def _filtered(d, allowed):
    return {
        k: v for k, v in (d or {}).items()
        if k in allowed and v not in (None, "")
    }


@transaction.atomic
def create_from_extraction(circuit, data):
    """
    Create a profile (+ endpoints + modulation targets) on ``circuit`` from a
    PCN data dict. Atomic: any model validation error rolls the whole thing back.
    Returns the created :class:`WirelessLicenseProfile`.
    """
    profile = WirelessLicenseProfile.objects.create(
        circuit=circuit, **_filtered(data.get("profile"), PROFILE_FIELDS)
    )
    for ep in (data.get("endpoints") or []):
        fields = _filtered(ep, ENDPOINT_FIELDS)
        if fields.get("side"):
            WirelessCircuitEndpoint.objects.create(
                wireless_license_profile=profile, **fields
            )
    for target in (data.get("modulation_targets") or []):
        fields = _filtered(target, TARGET_FIELDS)
        if fields.get("direction") and fields.get("modulation"):
            WirelessModulationTarget.objects.create(
                wireless_license_profile=profile, **fields
            )
    return profile
