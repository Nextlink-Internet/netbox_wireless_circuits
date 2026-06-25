from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.pcn_import import (
    create_circuit_and_profile,
    create_from_extraction,
)


class PCNImportMappingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        cls.ctype = CircuitType.objects.create(name="Microwave", slug="microwave")
        cls.circuit = Circuit.objects.create(
            cid="MW-PCN", provider=cls.provider, type=cls.ctype
        )

    def test_creates_profile_endpoints_targets(self):
        data = {
            "profile": {
                "frequency_band": "11 GHz", "pcn_number": "PCN-123",
                "receiver_threshold_dbm": -74.0,
                "bogus_key": "ignored",  # unknown -> dropped
                "licensee": "",          # empty -> dropped
            },
            "endpoints": [
                {"side": "A", "tx_frequency_mhz": 11200, "pcn_site_name": "Stiles"},
                {"side": "Z", "tx_frequency_mhz": 11700},
                {"pcn_site_name": "no side -> skipped"},
            ],
            "modulation_targets": [
                {"direction": "A_TO_Z", "modulation": "4096 QAM", "expected_rsl_dbm": -42},
                {"direction": "A_TO_Z"},  # no modulation -> skipped
            ],
        }
        profile = create_from_extraction(self.circuit, data)

        self.assertEqual(profile.circuit, self.circuit)
        self.assertEqual(profile.frequency_band, "11 GHz")
        self.assertEqual(profile.pcn_number, "PCN-123")
        self.assertEqual(profile.licensee, "")  # dropped empty -> model default blank
        self.assertEqual(profile.endpoints.count(), 2)
        self.assertEqual(profile.modulation_targets.count(), 1)
        target = profile.modulation_targets.first()
        self.assertEqual(target.modulation, "4096 QAM")
        # rank auto-filled from the canonical map on save
        self.assertEqual(target.modulation_rank, 100)

    def test_skeleton_like_minimal(self):
        profile = create_from_extraction(self.circuit, {"profile": {}})
        self.assertEqual(profile.circuit, self.circuit)
        self.assertEqual(profile.endpoints.count(), 0)

    def test_create_circuit_and_profile_wizard(self):
        data = {
            "profile": {"frequency_band": "11 GHz"},
            "endpoints": [{"side": "A"}, {"side": "Z"}],
            "modulation_targets": [{"direction": "A_TO_Z", "modulation": "256 QAM"}],
        }
        circuit, profile = create_circuit_and_profile(
            cid="MW-NEW-001", provider=self.provider, circuit_type=self.ctype, data=data,
        )
        self.assertEqual(circuit.cid, "MW-NEW-001")
        self.assertEqual(circuit.provider, self.provider)
        self.assertEqual(profile.circuit, circuit)
        self.assertEqual(profile.frequency_band, "11 GHz")
        self.assertEqual(profile.endpoints.count(), 2)
        self.assertEqual(profile.modulation_targets.count(), 1)
