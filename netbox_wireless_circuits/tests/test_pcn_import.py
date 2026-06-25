from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider
from dcim.models import Site

from netbox_wireless_circuits.models import WirelessLicenseProfile
from netbox_wireless_circuits.pcn_import import (
    create_circuit_and_profile,
    create_from_extraction,
    create_paths,
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

    def test_endpoint_netbox_site_injected(self):
        site = Site.objects.create(name="Throckmorton WE-1", slug="throck-we-1")
        data = {
            "profile": {"frequency_band": "11 GHz"},
            "endpoints": [
                {"side": "A", "netbox_site": site},
                {"side": "Z"},  # no site -> stays null
            ],
        }
        profile = create_from_extraction(self.circuit, data)
        ep_a = profile.endpoints.get(side="A")
        ep_z = profile.endpoints.get(side="Z")
        self.assertEqual(ep_a.netbox_site, site)
        self.assertIsNone(ep_z.netbox_site)

    def test_carrier_count_derives_radio_configuration(self):
        data = {"profile": {"frequency_band": "18 GHz", "carrier_count": 2}}
        profile = create_from_extraction(self.circuit, data)
        self.assertEqual(profile.carrier_count, 2)
        self.assertEqual(profile.radio_configuration, "2+0")

    def test_explicit_radio_configuration_is_kept(self):
        data = {"profile": {"carrier_count": 2, "radio_configuration": "1+1"}}
        profile = create_from_extraction(self.circuit, data)
        self.assertEqual(profile.radio_configuration, "1+1")

    def test_circuit_termination_created_from_assigned_site(self):
        from circuits.models import CircuitTermination

        site_a = Site.objects.create(name="Term Site A", slug="term-site-a")
        data = {
            "profile": {"frequency_band": "11 GHz"},
            "endpoints": [
                {"side": "A", "netbox_site": site_a},
                {"side": "Z"},  # no site -> no native termination
            ],
        }
        create_from_extraction(self.circuit, data)
        ct_a = CircuitTermination.objects.get(circuit=self.circuit, term_side="A")
        self.assertEqual(ct_a.termination, site_a)
        self.assertEqual(ct_a._site, site_a)  # denormalized so the site lists it
        self.assertFalse(
            CircuitTermination.objects.filter(
                circuit=self.circuit, term_side="Z"
            ).exists()
        )

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

    def test_create_paths_multi(self):
        data = {
            "paths": [
                {
                    "cid": "MW-HOP-1",
                    "profile": {"frequency_band": "11 GHz"},
                    "endpoints": [{"side": "A"}, {"side": "Z"}],
                    "modulation_targets": [{"direction": "A_TO_Z", "modulation": "4096 QAM"}],
                },
                {
                    "cid": "MW-HOP-2",
                    "profile": {"frequency_band": "11 GHz"},
                    "endpoints": [{"side": "A"}, {"side": "Z"}],
                    "modulation_targets": [],
                },
            ]
        }
        results = create_paths(self.provider, self.ctype, data)
        self.assertEqual(len(results), 2)
        cids = sorted(c.cid for c, _ in results)
        self.assertEqual(cids, ["MW-HOP-1", "MW-HOP-2"])
        self.assertEqual(results[0][1].endpoints.count(), 2)

    def test_create_paths_requires_cid(self):
        data = {"paths": [{"profile": {}, "endpoints": [], "modulation_targets": []}]}
        with self.assertRaises(ValueError):
            create_paths(self.provider, self.ctype, data)

    def test_import_sets_created_via_import(self):
        _, profile = create_circuit_and_profile(
            cid="MW-FLAG", provider=self.provider, circuit_type=self.ctype,
            data={"profile": {}},
        )
        self.assertTrue(profile.created_via_import)


class ProfileDeletionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        cls.ctype = CircuitType.objects.create(name="Microwave", slug="microwave")

    def test_deleting_imported_profile_deletes_circuit(self):
        circuit, profile = create_circuit_and_profile(
            cid="DEL-IMP", provider=self.provider, circuit_type=self.ctype,
            data={"profile": {}},
        )
        circuit_pk = circuit.pk
        profile.delete()
        self.assertFalse(Circuit.objects.filter(pk=circuit_pk).exists())

    def test_deleting_manual_profile_keeps_circuit(self):
        circuit = Circuit.objects.create(
            cid="DEL-MAN", provider=self.provider, type=self.ctype
        )
        # Not created via import -> circuit must survive profile deletion.
        profile = WirelessLicenseProfile.objects.create(circuit=circuit)
        profile.delete()
        self.assertTrue(Circuit.objects.filter(pk=circuit.pk).exists())

    def test_deleting_circuit_directly_cascades_without_error(self):
        circuit, profile = create_circuit_and_profile(
            cid="DEL-CASC", provider=self.provider, circuit_type=self.ctype,
            data={"profile": {}},
        )
        circuit_pk, profile_pk = circuit.pk, profile.pk
        circuit.delete()
        self.assertFalse(Circuit.objects.filter(pk=circuit_pk).exists())
        self.assertFalse(WirelessLicenseProfile.objects.filter(pk=profile_pk).exists())
