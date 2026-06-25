from django.db import IntegrityError, transaction
from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.choices import DEFAULT_RANKS
from netbox_wireless_circuits.models import (
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessModulationTarget,
)


class WirelessModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(
            name="Licensed Microwave", slug="licensed-microwave"
        )
        cls.circuit = Circuit.objects.create(
            cid="MW-TX-STILES-001", provider=provider, type=ctype,
        )

    def test_create_profile_from_circuit(self):
        profile = WirelessLicenseProfile.objects.create(circuit=self.circuit)
        self.assertEqual(self.circuit.wireless_license_profile, profile)
        self.assertEqual(str(profile), "Wireless License: MW-TX-STILES-001")

    def test_endpoint_side_uniqueness(self):
        profile = WirelessLicenseProfile.objects.create(circuit=self.circuit)
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=profile, side="A"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WirelessCircuitEndpoint.objects.create(
                    wireless_license_profile=profile, side="A"
                )
        # The opposite side remains allowed.
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=profile, side="Z"
        )
        self.assertEqual(profile.endpoints.count(), 2)

    def test_modulation_rank_autofill_when_blank(self):
        profile = WirelessLicenseProfile.objects.create(circuit=self.circuit)
        target = WirelessModulationTarget.objects.create(
            wireless_license_profile=profile,
            direction="A_TO_Z",
            modulation="256 QAM",
        )
        self.assertEqual(target.modulation_rank, DEFAULT_RANKS["256 QAM"])
        self.assertEqual(target.modulation_rank, 60)

    def test_modulation_rank_autofill_when_zero(self):
        profile = WirelessLicenseProfile.objects.create(circuit=self.circuit)
        target = WirelessModulationTarget.objects.create(
            wireless_license_profile=profile,
            direction="A_TO_Z",
            modulation="QPSK",
            modulation_rank=0,
        )
        self.assertEqual(target.modulation_rank, DEFAULT_RANKS["QPSK"])

    def test_modulation_rank_preserved_when_provided(self):
        profile = WirelessLicenseProfile.objects.create(circuit=self.circuit)
        target = WirelessModulationTarget.objects.create(
            wireless_license_profile=profile,
            direction="A_TO_Z",
            modulation="64 QAM",
            modulation_rank=42,
        )
        self.assertEqual(target.modulation_rank, 42)

    def test_modulation_uniqueness_per_direction(self):
        profile = WirelessLicenseProfile.objects.create(circuit=self.circuit)
        WirelessModulationTarget.objects.create(
            wireless_license_profile=profile, direction="A_TO_Z", modulation="256 QAM"
        )
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WirelessModulationTarget.objects.create(
                    wireless_license_profile=profile,
                    direction="A_TO_Z",
                    modulation="256 QAM",
                )
        # Same modulation in the opposite direction is allowed.
        target = WirelessModulationTarget.objects.create(
            wireless_license_profile=profile, direction="Z_TO_A", modulation="256 QAM"
        )
        self.assertIsNotNone(target.pk)
