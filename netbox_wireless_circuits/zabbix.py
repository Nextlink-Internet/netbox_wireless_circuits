"""
Pure computation for the Zabbix / nbxsync integration.

Turns a wireless link's licensed/expected design intent into the set of Zabbix
host **user macros** (and classification **tags**) that should be written to the
*receiving* radio's NetBox Device. A radio reports its own received signal level,
so the thresholds for a direction of travel belong on the receiving end:

    A_TO_Z  (A transmits, Z receives)  -> macros on side Z's device
    Z_TO_A  (Z transmits, A receives)  -> macros on side A's device

This module has **no dependency on nbxsync**: it only computes the desired
macro/tag specs. The code that writes them into nbxsync models lives in
``nbxsync_sync.py`` and is a soft (optional) dependency.
"""
from .choices import EndpointSideChoices, ModulationDirectionChoices

# Receiving endpoint side for each direction of travel.
RX_SIDE = {
    ModulationDirectionChoices.A_TO_Z: EndpointSideChoices.SIDE_Z,
    ModulationDirectionChoices.Z_TO_A: EndpointSideChoices.SIDE_A,
}
# Inverse: given the side a device sits on, which direction does it receive?
RX_DIRECTION_FOR_SIDE = {side: direction for direction, side in RX_SIDE.items()}


def sanitize_prefix(prefix):
    """Normalize a user-entered macro prefix (strip whitespace and stray {$}})."""
    cleaned = (prefix or "").strip().strip("{}$ ").strip()
    return cleaned or "WL"


def effective_warning_rsl(target, tolerance):
    """expected_rsl - (warning_margin + global_tolerance); None if no expected."""
    if target.expected_rsl_dbm is None:
        return None
    return target.expected_rsl_dbm - ((target.warning_margin_db or 0) + tolerance)


def effective_critical_rsl(target, tolerance):
    """expected_rsl - (critical_margin + global_tolerance); None if no expected."""
    if target.expected_rsl_dbm is None:
        return None
    return target.expected_rsl_dbm - ((target.critical_margin_db or 0) + tolerance)


def top_enabled_target(profile, direction):
    """Highest-ranked alarm-enabled modulation target for a direction, or None."""
    targets = profile.modulation_targets.filter(direction=direction).order_by(
        "-modulation_rank"
    )
    return next((t for t in targets if t.alarm_enabled), None)


def active_exception(profile):
    """The first currently-active per-link exception, or None."""
    return next((e for e in profile.exceptions.all() if e.is_active), None)


def macro_values_for_direction(profile, direction, tolerance, exception):
    """
    Compute the {suffix: value} macro map for one receiving direction.

    Returns an empty dict if there is no alarm-enabled modulation target (nothing
    to publish). Values are native (Decimal / int / str); the writer stringifies.
    """
    top = top_enabled_target(profile, direction)
    if top is None:
        return {}

    values = {
        "RSL.EXPECTED": top.expected_rsl_dbm,
        "RSL.WARN": effective_warning_rsl(top, tolerance),
        "RSL.CRIT": effective_critical_rsl(top, tolerance),
        "MOD.TOP": top.modulation,
        "MOD.TOP_RANK": top.modulation_rank,
        "ALARM.SUPPRESS": 1 if (exception and exception.suppress_alarms) else 0,
        "CID": profile.circuit.cid,
    }
    # An active exception may set an agreed achievable RSL to alarm against
    # instead of the PCN target; surface it as its own macro (the Zabbix
    # template decides how to use it). The PCN target stays authoritative.
    if exception and exception.adjusted_rsl_dbm is not None:
        values["RSL.ADJUSTED"] = exception.adjusted_rsl_dbm

    return {k: v for k, v in values.items() if v is not None}


def device_endpoints(device):
    """Wireless endpoints anchored to this device (it is the radio host)."""
    from .models import WirelessCircuitEndpoint

    return list(
        WirelessCircuitEndpoint.objects.filter(netbox_device=device).select_related(
            "wireless_license_profile",
            "wireless_license_profile__circuit",
            "netbox_interface",
        )
    )


def _macro_context(endpoint, multi):
    """Context for a macro on a multi-radio host (empty for single-link hosts)."""
    if not multi:
        return ""
    if endpoint.netbox_interface:
        return endpoint.netbox_interface.name
    return endpoint.wireless_license_profile.circuit.cid


def device_sync_plan(device, settings):
    """
    Desired Zabbix macros + tags for a device, derived from every wireless link
    it terminates as the receiver.

    Returns ``{"macros": [{name, context, value}], "tags": [{tag, value}]}``.
    All values are strings. ``name`` is the full Zabbix macro, e.g.
    ``{$WL.RSL.WARN}`` (context, if any, is carried separately).
    """
    prefix = sanitize_prefix(settings.zabbix_macro_prefix)
    tolerance = settings.effective_tolerance_db
    endpoints = device_endpoints(device)
    multi = len(endpoints) > 1

    macros = []
    tags = []
    seen_tags = set()
    for ep in endpoints:
        direction = RX_DIRECTION_FOR_SIDE.get(ep.side)
        if direction is None:
            continue
        profile = ep.wireless_license_profile
        exception = active_exception(profile)
        values = macro_values_for_direction(profile, direction, tolerance, exception)
        if not values:
            continue
        context = _macro_context(ep, multi)
        for suffix, value in values.items():
            macros.append({
                "name": f"{{${prefix}.{suffix}}}",
                "context": context,
                "value": str(value),
            })
        if settings.zabbix_emit_tags:
            for tag, value in (
                ("wireless-circuit", profile.circuit.cid),
                ("wireless-band", profile.frequency_band or None),
            ):
                if value and (tag, value) not in seen_tags:
                    seen_tags.add((tag, value))
                    tags.append({"tag": tag, "value": value})

    return {"macros": macros, "tags": tags}


def devices_for_profile(profile):
    """Distinct radio Devices a profile's endpoints are anchored to."""
    devices = {}
    for ep in profile.endpoints.all():
        if ep.netbox_device_id:
            devices[ep.netbox_device_id] = ep.netbox_device
    return list(devices.values())
