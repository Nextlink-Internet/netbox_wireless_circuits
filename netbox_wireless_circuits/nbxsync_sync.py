"""
Soft-dependency integration that writes wireless link design intent into
**nbxsync** as Zabbix host user-macro assignments (and classification tags) on
the receiving radio's NetBox Device.

Ownership model (decided with the operator): the ``{$WL.*}`` macro *definitions*
live in the operator's Zabbix "wireless" template, imported into nbxsync as
``ZabbixMacro`` rows. This plugin only writes the per-device **values**
(``ZabbixMacroAssignment``) referencing those definitions, looked up by macro
name. If a definition is missing (template not imported yet), that macro is
skipped and reported — the sync is best-effort and never raises into the request.

Tags are fully owned here: ``ZabbixTag`` carries the value, ``ZabbixTagAssignment``
binds it to the device.

Everything is guarded by :func:`sync_enabled` so the plugin runs fine without
nbxsync installed and stays dormant until an operator turns the sync on.
"""
import logging

from django.apps import apps

from .models import WirelessGlobalSettings
from .zabbix import device_sync_plan, devices_for_profile, sanitize_prefix

logger = logging.getLogger("netbox_wireless_circuits")

# nbxsync tag keys this plugin manages (for safe stale cleanup).
MANAGED_TAG_KEYS = {"wireless-circuit", "wireless-band"}


def nbxsync_available():
    return apps.is_installed("nbxsync")


def sync_enabled(settings=None):
    """True only when nbxsync is installed and the operator enabled the sync."""
    if not nbxsync_available():
        return False
    settings = settings or WirelessGlobalSettings.load()
    return bool(settings.zabbix_sync_enabled)


def _content_type_for(obj):
    from django.contrib.contenttypes.models import ContentType

    return ContentType.objects.get_for_model(obj.__class__)


def sync_device(device, settings=None):
    """
    Reconcile this device's ``{$<prefix>.*}`` macro assignments and tags with the
    current design intent of the wireless links it receives.

    Returns a summary dict. Best-effort: logs and returns on any failure.
    """
    summary = {
        "device": str(device),
        "skipped": False,
        "macros_written": 0,
        "macros_missing_def": [],
        "macros_deleted": 0,
        "tags_written": 0,
        "tags_deleted": 0,
    }
    settings = settings or WirelessGlobalSettings.load()
    if not sync_enabled(settings):
        summary["skipped"] = True
        return summary

    try:
        from nbxsync.models import (
            ZabbixMacro,
            ZabbixMacroAssignment,
            ZabbixTag,
            ZabbixTagAssignment,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("nbxsync import failed; skipping sync: %s", exc)
        summary["skipped"] = True
        return summary

    plan = device_sync_plan(device, settings)
    ct = _content_type_for(device)
    prefix = sanitize_prefix(settings.zabbix_macro_prefix)
    managed_macro_prefix = f"{{${prefix}."

    # --- macros ---
    desired_macro_keys = set()
    for spec in plan["macros"]:
        name, context, value = spec["name"], spec["context"], spec["value"]
        desired_macro_keys.add((name, context))
        macro_def = ZabbixMacro.objects.filter(macro=name).first()
        if macro_def is None:
            # Template-owned definition not present yet; nothing to bind to.
            summary["macros_missing_def"].append(name)
            continue
        assignment, created = ZabbixMacroAssignment.objects.get_or_create(
            zabbixmacro=macro_def,
            assigned_object_type=ct,
            assigned_object_id=device.pk,
            context=context,
            is_regex=False,
            defaults={"value": value},
        )
        if not created and assignment.value != value:
            assignment.value = value
            assignment.save()
        summary["macros_written"] += 1

    # Stale macro cleanup: drop our-prefixed assignments no longer desired.
    existing = ZabbixMacroAssignment.objects.filter(
        assigned_object_type=ct,
        assigned_object_id=device.pk,
        zabbixmacro__macro__startswith=managed_macro_prefix,
    ).select_related("zabbixmacro")
    for assignment in existing:
        if (assignment.zabbixmacro.macro, assignment.context) not in desired_macro_keys:
            assignment.delete()
            summary["macros_deleted"] += 1

    # --- tags ---
    if settings.zabbix_emit_tags:
        desired_tag_pairs = set()
        for spec in plan["tags"]:
            tag, value = spec["tag"], spec["value"]
            desired_tag_pairs.add((tag, value))
            ztag, _ = ZabbixTag.objects.get_or_create(
                tag=tag,
                value=value,
                defaults={"name": f"{tag}={value}"},
            )
            ZabbixTagAssignment.objects.get_or_create(
                zabbixtag=ztag,
                assigned_object_type=ct,
                assigned_object_id=device.pk,
            )
            summary["tags_written"] += 1

        existing_tags = ZabbixTagAssignment.objects.filter(
            assigned_object_type=ct,
            assigned_object_id=device.pk,
            zabbixtag__tag__in=MANAGED_TAG_KEYS,
        ).select_related("zabbixtag")
        for ta in existing_tags:
            if (ta.zabbixtag.tag, ta.zabbixtag.value) not in desired_tag_pairs:
                ta.delete()
                summary["tags_deleted"] += 1

    return summary


def sync_profile(profile, settings=None):
    """Sync every receiving device a profile's endpoints anchor to."""
    settings = settings or WirelessGlobalSettings.load()
    results = []
    if not sync_enabled(settings):
        return results
    for device in devices_for_profile(profile):
        try:
            results.append(sync_device(device, settings))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("wireless zabbix sync failed for %s: %s", device, exc)
    return results


def resync_all(settings=None):
    """
    Full reconcile: visit every device that terminates a wireless endpoint.

    Used by the management command and the global-settings change signal.
    """
    settings = settings or WirelessGlobalSettings.load()
    results = []
    if not sync_enabled(settings):
        return results

    from .models import WirelessCircuitEndpoint

    device_ids = (
        WirelessCircuitEndpoint.objects.filter(netbox_device__isnull=False)
        .values_list("netbox_device_id", flat=True)
        .distinct()
    )
    from dcim.models import Device

    for device in Device.objects.filter(pk__in=list(device_ids)):
        try:
            results.append(sync_device(device, settings))
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("wireless zabbix sync failed for %s: %s", device, exc)
    return results
