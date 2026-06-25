from decimal import Decimal

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from django.test.utils import override_settings
from unittest import skipUnless

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.models import (
    WirelessBandTolerance,
    WirelessCircuitEndpoint,
    WirelessGlobalSettings,
    WirelessLicenseProfile,
    WirelessModulationTarget,
)
from netbox_wireless_circuits.nbxsync_sync import sync_device

from .test_zabbix import make_device

NBXSYNC = apps.is_installed("nbxsync")

# Macro names our plugin emits with the default "WL" prefix.
MACRO_NAMES = [
    "{$WL.RSL.EXPECTED}", "{$WL.RSL.WARN}", "{$WL.RSL.CRIT}",
    "{$WL.MOD.TOP}", "{$WL.MOD.TOP_RANK}", "{$WL.ALARM.SUPPRESS}", "{$WL.CID}",
]


@skipUnless(NBXSYNC, "nbxsync is not installed")
class NbxsyncMacroSyncTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(name="Microwave", slug="microwave")
        circuit = Circuit.objects.create(cid="MW-Z", provider=provider, type=ctype)
        cls.profile = WirelessLicenseProfile.objects.create(
            circuit=circuit, frequency_band="11 GHz"
        )
        cls.device = make_device("RX")
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=cls.profile, side="Z", netbox_device=cls.device,
        )
        cls.target = WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile, direction="A_TO_Z",
            modulation="4096 QAM", expected_rsl_dbm=Decimal("-42"),
            warning_margin_db=Decimal("3"), critical_margin_db=Decimal("6"),
            alarm_enabled=True,
        )

    def setUp(self):
        from nbxsync.models import ZabbixMacro

        # Install seeds default band rules; clear so the global default (0) applies
        # and the expected RSL math below is deterministic.
        WirelessBandTolerance.objects.all().delete()

        # Template-owned macro defs are simulated as owner-less ZabbixMacro rows;
        # sync looks them up by macro string regardless of owner.
        for name in MACRO_NAMES:
            ZabbixMacro.objects.get_or_create(macro=name, defaults={"type": "0"})

        self.settings = WirelessGlobalSettings.load()
        self.settings.zabbix_sync_enabled = True
        self.settings.zabbix_macro_prefix = "WL"
        self.settings.zabbix_emit_tags = True
        self.settings.save()
        self.ct = ContentType.objects.get_for_model(self.device.__class__)

    def _assignments(self):
        from nbxsync.models import ZabbixMacroAssignment

        return ZabbixMacroAssignment.objects.filter(
            assigned_object_type=self.ct, assigned_object_id=self.device.pk
        )

    def test_writes_macro_assignments_with_values(self):
        summary = sync_device(self.device, self.settings)
        self.assertFalse(summary["skipped"])
        self.assertEqual(summary["macros_missing_def"], [])
        by_macro = {a.zabbixmacro.macro: a.value for a in self._assignments()}
        self.assertEqual(by_macro["{$WL.RSL.EXPECTED}"], "-42.000")
        self.assertEqual(by_macro["{$WL.RSL.WARN}"], "-45.000")
        self.assertEqual(by_macro["{$WL.RSL.CRIT}"], "-48.000")
        self.assertEqual(by_macro["{$WL.MOD.TOP}"], "4096 QAM")
        self.assertEqual(by_macro["{$WL.CID}"], "MW-Z")

    def test_idempotent(self):
        sync_device(self.device, self.settings)
        first = self._assignments().count()
        sync_device(self.device, self.settings)
        self.assertEqual(self._assignments().count(), first)

    def test_value_update_in_place(self):
        sync_device(self.device, self.settings)
        self.target.expected_rsl_dbm = Decimal("-40")
        self.target.save()
        sync_device(self.device, self.settings)
        warn = self._assignments().get(zabbixmacro__macro="{$WL.RSL.WARN}")
        self.assertEqual(warn.value, "-43.000")

    def test_stale_macro_removed(self):
        sync_device(self.device, self.settings)
        self.assertTrue(self._assignments().filter(
            zabbixmacro__macro="{$WL.RSL.WARN}"
        ).exists())
        # Drop expected RSL: WARN/CRIT/EXPECTED values become None -> not desired.
        # (save() also fires the resync signal; a manual sync confirms the end state.)
        self.target.expected_rsl_dbm = None
        self.target.save()
        sync_device(self.device, self.settings)
        self.assertFalse(self._assignments().filter(
            zabbixmacro__macro="{$WL.RSL.WARN}"
        ).exists())

    def test_tags_written(self):
        from nbxsync.models import ZabbixTagAssignment

        sync_device(self.device, self.settings)
        tags = ZabbixTagAssignment.objects.filter(
            assigned_object_type=self.ct, assigned_object_id=self.device.pk
        )
        pairs = {(t.zabbixtag.tag, t.zabbixtag.value) for t in tags}
        self.assertIn(("wireless-circuit", "MW-Z"), pairs)
        self.assertIn(("wireless-band", "11 GHz"), pairs)

    def test_disabled_is_skipped(self):
        from nbxsync.models import ZabbixMacroAssignment

        # Clear anything a prior enabled save may have synced via signals.
        self.settings.zabbix_sync_enabled = False
        self.settings.save()  # disabled -> signal is a no-op
        ZabbixMacroAssignment.objects.all().delete()
        summary = sync_device(self.device, self.settings)
        self.assertTrue(summary["skipped"])
        self.assertEqual(self._assignments().count(), 0)
