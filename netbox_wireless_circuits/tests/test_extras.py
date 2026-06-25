from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.models import (
    WirelessGlobalSettings,
    WirelessLicenseProfile,
    WirelessTargetException,
)


class WirelessGlobalSettingsTests(TestCase):
    def test_singleton(self):
        s1 = WirelessGlobalSettings.load()
        s2 = WirelessGlobalSettings.load()
        self.assertEqual(s1.pk, 1)
        self.assertEqual(s1.pk, s2.pk)
        self.assertEqual(WirelessGlobalSettings.objects.count(), 1)

    def test_effective_tolerance_respects_enabled(self):
        s = WirelessGlobalSettings.load()
        s.global_tolerance_db = Decimal("2")
        s.tolerance_enabled = True
        s.save()
        self.assertEqual(WirelessGlobalSettings.load().effective_tolerance_db, Decimal("2.00"))
        s.tolerance_enabled = False
        s.save()
        self.assertEqual(WirelessGlobalSettings.load().effective_tolerance_db, Decimal("0"))


class WirelessTargetExceptionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(
            name="Licensed Microwave", slug="licensed-microwave"
        )
        circuit = Circuit.objects.create(
            cid="MW-TX-STILES-001", provider=provider, type=ctype
        )
        cls.profile = WirelessLicenseProfile.objects.create(circuit=circuit)

    def _exc(self, **kwargs):
        return WirelessTargetException.objects.create(
            wireless_license_profile=self.profile, reason="test", **kwargs
        )

    def test_active_when_enabled_no_dates(self):
        self.assertTrue(self._exc(enabled=True).is_active)

    def test_inactive_when_disabled(self):
        self.assertFalse(self._exc(enabled=False).is_active)

    def test_inactive_when_expired(self):
        e = self._exc(enabled=True, expiry_date=date.today() - timedelta(days=1))
        self.assertFalse(e.is_active)

    def test_inactive_before_effective(self):
        e = self._exc(enabled=True, effective_date=date.today() + timedelta(days=1))
        self.assertFalse(e.is_active)

    def test_active_within_window(self):
        e = self._exc(
            enabled=True,
            effective_date=date.today() - timedelta(days=1),
            expiry_date=date.today() + timedelta(days=1),
        )
        self.assertTrue(e.is_active)
