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
from decimal import Decimal, InvalidOperation

from circuits.models import Circuit

from .. import pcn_import
from ..models import WirelessLicenseProfile

logger = logging.getLogger("netbox_wireless_circuits")

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


def run_import(source, file_obj, *, provider, circuit_type, status="active",
               apply_changes=False, progress=None):
    """
    Import every link the ``source`` yields from ``file_obj``.

    Returns a report dict::

        {"source", "total", "created":[...], "changed":[...],
         "unchanged": int, "errors":[...]}

    ``apply_changes`` is reserved for a future write-on-update mode; the current
    policy reports changes on existing links without modifying them.
    """
    report = {
        "source": source.name,
        "total": 0,
        "created": [],
        "changed": [],
        "unchanged": 0,
        "errors": [],
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
                circuit, _ = _create_link(
                    parsed, source.name, provider, circuit_type, status
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
