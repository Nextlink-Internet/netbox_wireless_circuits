"""
Signal receivers that keep the nbxsync macro/tag assignments in step with the
plugin's design intent. All work is gated by ``sync_enabled`` (nbxsync installed
AND the operator-enabled flag), so these are near-no-ops by default.
"""
import logging
import threading

from circuits.models import Circuit
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import (
    WirelessCircuitEndpoint,
    WirelessGlobalSettings,
    WirelessLicenseProfile,
    WirelessModulationTarget,
    WirelessTargetException,
)
from .nbxsync_sync import resync_all, sync_device, sync_enabled, sync_profile

logger = logging.getLogger("netbox_wireless_circuits")

# Circuit PKs whose deletion is currently in flight, so the profile post_delete
# below doesn't try to re-delete a circuit that's already being removed (which
# would happen when the user deletes the Circuit directly and it cascades to
# the profile). Thread-local to stay correct under concurrent requests.
_circuit_deletes = threading.local()


def _circuits_in_flight():
    pks = getattr(_circuit_deletes, "pks", None)
    if pks is None:
        pks = _circuit_deletes.pks = set()
    return pks


@receiver(pre_delete, sender=Circuit)
def _mark_circuit_deleting(sender, instance, **kwargs):
    _circuits_in_flight().add(instance.pk)


@receiver(post_delete, sender=Circuit)
def _unmark_circuit_deleting(sender, instance, **kwargs):
    _circuits_in_flight().discard(instance.pk)


@receiver(post_delete, sender=WirelessLicenseProfile)
def _delete_imported_circuit(sender, instance, **kwargs):
    """
    Deleting a wizard-imported profile also deletes the circuit it created
    (and its terminations). Skipped when the circuit deletion is what triggered
    this (cascade), and never touches manually-attached circuits.
    """
    if not getattr(instance, "created_via_import", False):
        return
    circuit_id = instance.circuit_id
    if not circuit_id or circuit_id in _circuits_in_flight():
        return
    try:
        Circuit.objects.filter(pk=circuit_id).delete()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("wireless: could not delete imported circuit %s: %s",
                       circuit_id, exc)


def _profile_of(instance):
    if isinstance(instance, WirelessLicenseProfile):
        return instance
    return getattr(instance, "wireless_license_profile", None)


@receiver(post_save, sender=WirelessLicenseProfile)
@receiver(post_save, sender=WirelessModulationTarget)
@receiver(post_save, sender=WirelessTargetException)
@receiver(post_delete, sender=WirelessModulationTarget)
@receiver(post_delete, sender=WirelessTargetException)
def _resync_profile(sender, instance, **kwargs):
    if not sync_enabled():
        return
    profile = _profile_of(instance)
    if profile is not None:
        try:
            sync_profile(profile)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("wireless zabbix profile sync failed: %s", exc)


@receiver(post_save, sender=WirelessCircuitEndpoint)
@receiver(post_delete, sender=WirelessCircuitEndpoint)
def _resync_endpoint(sender, instance, **kwargs):
    if not sync_enabled():
        return
    # Sync the endpoint's own device directly so a removed/relocated endpoint
    # gets its stale macros cleaned even when the profile no longer points here.
    device = getattr(instance, "netbox_device", None)
    if device is not None:
        try:
            sync_device(device)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("wireless zabbix endpoint sync failed: %s", exc)
    profile = _profile_of(instance)
    if profile is not None:
        try:
            sync_profile(profile)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("wireless zabbix endpoint sync failed: %s", exc)


@receiver(post_save, sender=WirelessGlobalSettings)
def _resync_all(sender, instance, **kwargs):
    # Prefix / tolerance / enable toggles affect every link.
    if not sync_enabled(instance):
        return
    try:
        resync_all(instance)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("wireless zabbix global resync failed: %s", exc)
