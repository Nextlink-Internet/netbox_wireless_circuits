"""
Source-agnostic import engine.

Consumes :class:`~.base.ParsedLink` objects from any source adapter and applies
the de-duplication policy: a link whose ``(import_source, import_key)`` is not yet
present is **created** (circuit + profile + endpoints + modulation targets); a link
that already exists is **diffed and reported, not modified** (the operator reviews
the change report and decides). New-link creation reuses the PCN importer's atomic
create path, so each link is all-or-nothing and a bad row can't abort the batch.
"""
import logging
import re
from decimal import Decimal, InvalidOperation

from circuits.models import Circuit, CircuitType
from django.utils.text import slugify

from .. import pcn_import
from ..models import WirelessLicenseProfile

logger = logging.getLogger("netbox_wireless_circuits")


def _normalize_site_name(name):
    """Uppercase, strip non-alphanumerics — so 'BENBROOK LAKE' == 'BENBROOKLAKE'."""
    return re.sub(r"[^A-Z0-9]", "", (name or "").upper())


def _load_site_map():
    """
    Map normalized NetBox Site name -> Site, for matching coordinator site names
    to existing sites. Built once per import. Ambiguous normalized names keep the
    first match (rare); unmatched coordinator sites simply stay unlinked.
    """
    from dcim.models import Site

    site_map = {}
    for site in Site.objects.all().only("id", "name"):
        key = _normalize_site_name(site.name)
        if key:
            site_map.setdefault(key, site)
    return site_map


def _resolve_endpoint_sites(parsed, site_map):
    """
    Best-effort: link each endpoint to a NetBox Site by matching its
    ``pcn_site_name`` (normalized). A matched Site is injected as ``netbox_site``
    so the create path also builds the native A/Z CircuitTermination.
    """
    for ep in parsed.data.get("endpoints", []):
        if not ep or ep.get("netbox_site"):
            continue
        site = site_map.get(_normalize_site_name(ep.get("pcn_site_name")))
        if site is not None:
            ep["netbox_site"] = site

# Built-in fallback mapping (operational circuit status per FCC license status),
# used only if the operator-editable WirelessImportStatusMap table is empty.
# The table (seeded with these same defaults) is the source of truth at runtime.
LICENSE_TO_CIRCUIT_STATUS = {
    "licensed": "active",
    "temporary": "active",
    "applied": "planned",
    "proposed": "planned",
    "transitional": "planned",
    "questionable": "planned",
    "protection_declined": "planned",
    "replaced": "decommissioned",
    "expired_terminated": "decommissioned",
}


def _load_status_map():
    """Operator-configured license→circuit status map (enabled rows), or defaults."""
    from ..models import WirelessImportStatusMap

    rows = dict(
        WirelessImportStatusMap.objects.filter(enabled=True)
        .values_list("license_status", "circuit_status")
    )
    return rows or dict(LICENSE_TO_CIRCUIT_STATUS)


def _derive_status(profile_data, fallback, status_map):
    license_status = (profile_data or {}).get("registration_status") or ""
    return status_map.get(license_status, fallback)


def _resolve_circuit_type(source, circuit_type):
    """Use the explicit circuit type, else get-or-create the source's default."""
    if circuit_type is not None:
        return circuit_type
    name = getattr(source, "default_circuit_type", None)
    if not name:
        raise ValueError(
            "No circuit type provided and the import source declares no default."
        )
    ct, _ = CircuitType.objects.get_or_create(
        name=name, defaults={"slug": slugify(name)}
    )
    return ct

# Fields compared when reporting changes on an existing link. Operator-owned
# data (NetBox site/device/interface links, tags, exceptions, antenna catalog
# enrichment) is deliberately excluded — the import never touches it.
_PROFILE_DIFF_FIELDS = sorted(pcn_import.PROFILE_FIELDS)
_ENDPOINT_DIFF_FIELDS = sorted(pcn_import.ENDPOINT_FIELDS - {"side"})
_TARGET_DIFF_FIELDS = sorted(pcn_import.TARGET_FIELDS - {"direction", "modulation"})


def _scalar_eq(a, b):
    """Compare two values tolerant of Decimal/str/None and blank-vs-None."""
    if a in (None, "") and b in (None, ""):
        return True
    if a in (None, "") or b in (None, ""):
        return False
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except (InvalidOperation, ValueError, ArithmeticError):
        return str(a).strip() == str(b).strip()


def _unique_cid(base):
    """Return ``base`` or a suffixed variant not yet used by any Circuit."""
    base = (base or "MW link").strip()[:90]
    if not Circuit.objects.filter(cid=base).exists():
        return base
    for i in range(2, 1000):
        candidate = f"{base} ({i})"
        if not Circuit.objects.filter(cid=candidate).exists():
            return candidate
    raise ValueError(f"Could not derive a unique CID from {base!r}")


def _create_link(parsed, source_name, provider, circuit_type, status):
    cid = _unique_cid(parsed.cid)
    circuit, profile = pcn_import.create_circuit_and_profile(
        cid=cid,
        provider=provider,
        circuit_type=circuit_type,
        data=parsed.data,
        status=status,
        extra_profile={
            "import_source": source_name,
            "import_key": parsed.key,
            "import_link_id": parsed.link_id or "",
        },
    )
    return circuit, profile


def _diff_existing(profile, parsed):
    """Yield human-readable change rows between stored profile and parsed link."""
    changes = []

    for k in _PROFILE_DIFF_FIELDS:
        if k not in parsed.data.get("profile", {}):
            continue
        new = parsed.data["profile"][k]
        old = getattr(profile, k, None)
        if not _scalar_eq(old, new):
            changes.append({"scope": "profile", "field": k,
                            "old": _fmt(old), "new": _fmt(new)})

    stored_eps = {ep.side: ep for ep in profile.endpoints.all()}
    for ep in parsed.data.get("endpoints", []):
        side = ep.get("side")
        stored = stored_eps.get(side)
        if stored is None:
            changes.append({"scope": f"endpoint {side}", "field": "(missing)",
                            "old": "—", "new": "present in import"})
            continue
        for k in _ENDPOINT_DIFF_FIELDS:
            if k not in ep:
                continue
            old = getattr(stored, k, None)
            if not _scalar_eq(old, ep[k]):
                changes.append({"scope": f"endpoint {side}", "field": k,
                                "old": _fmt(old), "new": _fmt(ep[k])})

    stored_t = {(t.direction, t.modulation): t for t in profile.modulation_targets.all()}
    for t in parsed.data.get("modulation_targets", []):
        ident = (t.get("direction"), t.get("modulation"))
        stored = stored_t.get(ident)
        if stored is None:
            changes.append({"scope": f"target {ident[0]}/{ident[1]}",
                            "field": "(missing)", "old": "—", "new": "present in import"})
            continue
        for k in _TARGET_DIFF_FIELDS:
            if k not in t:
                continue
            old = getattr(stored, k, None)
            if not _scalar_eq(old, t[k]):
                changes.append({"scope": f"target {ident[0]}/{ident[1]}", "field": k,
                                "old": _fmt(old), "new": _fmt(t[k])})
    return changes


def _fmt(v):
    if v in (None, ""):
        return "—"
    return str(v)


def run_import(source, file_obj, *, provider, circuit_type=None, status="active",
               apply_changes=False, progress=None):
    """
    Import every link the ``source`` yields from ``file_obj``.

    ``circuit_type`` may be None — the source's ``default_circuit_type`` is then
    get-or-created (e.g. Comsearch → "Licensed Microwave"). ``status`` is only a
    fallback: each new circuit's operational status is derived from its FCC
    license status (see :data:`LICENSE_TO_CIRCUIT_STATUS`).

    Returns a report dict::

        {"source", "total", "created":[...], "changed":[...],
         "unchanged": int, "errors":[...]}

    ``apply_changes`` is reserved for a future write-on-update mode; the current
    policy reports changes on existing links without modifying them.
    """
    effective_type = _resolve_circuit_type(source, circuit_type)
    status_map = _load_status_map()
    site_map = _load_site_map()
    report = {
        "source": source.name,
        "total": 0,
        "created": [],
        "changed": [],
        "unchanged": 0,
        "errors": [],
        "sites_linked": 0,
        "sites_unmatched": 0,
    }
    for parsed in source.iter_links(file_obj):
        report["total"] += 1
        try:
            existing = (
                WirelessLicenseProfile.objects
                .filter(import_source=source.name, import_key=parsed.key)
                .select_related("circuit")
                .first()
            )
            if existing is None:
                _resolve_endpoint_sites(parsed, site_map)
                for ep in parsed.data.get("endpoints", []):
                    if ep.get("pcn_site_name"):
                        if ep.get("netbox_site"):
                            report["sites_linked"] += 1
                        else:
                            report["sites_unmatched"] += 1
                link_status = _derive_status(
                    parsed.data.get("profile"), status, status_map
                )
                circuit, _ = _create_link(
                    parsed, source.name, provider, effective_type, link_status
                )
                report["created"].append({"cid": circuit.cid, "key": parsed.key})
            else:
                diffs = _diff_existing(existing, parsed)
                if diffs:
                    report["changed"].append({
                        "cid": existing.circuit.cid,
                        "key": parsed.key,
                        "changes": diffs,
                    })
                else:
                    report["unchanged"] += 1
        except Exception as exc:  # one bad row must not abort the batch
            logger.warning("comsearch import: link %s failed: %s", parsed.key, exc)
            report["errors"].append({
                "key": parsed.key,
                "cid": getattr(parsed, "cid", ""),
                "error": str(exc),
            })
        if progress is not None and report["total"] % 100 == 0:
            progress(report["total"])
    return report
