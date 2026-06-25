from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.models import (
    WirelessBandTolerance,
    WirelessCircuitEndpoint,
    WirelessGlobalSettings,
    WirelessLicenseProfile,
    WirelessLLMProvider,
    WirelessModulationTarget,
    WirelessTargetException,
)

User = get_user_model()

BASE = "/api/plugins/wireless-circuits"


class WirelessAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(
            name="Licensed Microwave", slug="licensed-microwave"
        )
        cls.circuit = Circuit.objects.create(
            cid="MW-TX-STILES-001", provider=provider, type=ctype
        )
        cls.profile = WirelessLicenseProfile.objects.create(
            circuit=cls.circuit,
            frequency_band="11 GHz",
            receiver_threshold_dbm="-74.0",
        )
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=cls.profile,
            side="A",
            tx_frequency_mhz="11200.000",
        )
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=cls.profile,
            side="Z",
            tx_frequency_mhz="11700.000",
        )
        # A_TO_Z ladder: 4096 QAM (rank 100), 256 QAM (rank 60)
        cls.top = WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile,
            direction="A_TO_Z",
            modulation="4096 QAM",
            data_rate_kbps=1000000,
            max_power_dbm="23.0",
            eirp_dbm="55.0",
            expected_rsl_dbm="-42.0",
            alarm_enabled=True,
        )
        WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile,
            direction="A_TO_Z",
            modulation="256 QAM",
            alarm_enabled=True,
        )
        WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile,
            direction="Z_TO_A",
            modulation="64 QAM",
            alarm_enabled=False,
        )

    def setUp(self):
        self.user = User.objects.create_user(username="apitester", is_superuser=True)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    # --- list / retrieve ---

    def test_list_profiles(self):
        r = self.client.get(f"{BASE}/wireless-license-profiles/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 1)

    def test_retrieve_profile_with_nested(self):
        r = self.client.get(f"{BASE}/wireless-license-profiles/{self.profile.pk}/")
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertEqual(data["circuit"]["cid"], "MW-TX-STILES-001")
        self.assertEqual(len(data["endpoints"]), 2)
        self.assertEqual(len(data["modulation_targets"]), 3)

    def test_list_endpoints(self):
        r = self.client.get(f"{BASE}/wireless-circuit-endpoints/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)

    def test_list_modulation_targets(self):
        r = self.client.get(f"{BASE}/wireless-modulation-targets/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 3)

    # --- filtering ---

    def test_filter_profile_by_circuit_id(self):
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/?circuit_id={self.circuit.pk}"
        )
        self.assertEqual(r.json()["count"], 1)

    def test_filter_profile_by_cid(self):
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/?circuit_cid=MW-TX-STILES"
        )
        self.assertEqual(r.json()["count"], 1)

    def test_filter_modulation_targets_by_direction_and_alarm(self):
        r = self.client.get(
            f"{BASE}/wireless-modulation-targets/"
            f"?direction=A_TO_Z&alarm_enabled=true"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["count"], 2)

    # --- zabbix action ---

    def test_zabbix_single_direction_keys(self):
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/{self.profile.pk}/zabbix/"
            f"?direction=A_TO_Z"
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        expected_keys = {
            "circuit_id", "cid", "band", "direction", "frequency_mhz",
            "top_modulation", "top_modulation_rank", "receiver_threshold_dbm",
            "carrier_count", "radio_configuration", "aggregate_data_rate_kbps",
            "modulation_targets", "global_tolerance_db", "exception",
        }
        self.assertEqual(set(data.keys()), expected_keys)
        self.assertEqual(data["cid"], "MW-TX-STILES-001")
        self.assertEqual(data["band"], "11 GHz")
        self.assertEqual(data["direction"], "A_TO_Z")
        self.assertEqual(data["frequency_mhz"], "11200.000")
        self.assertEqual(data["top_modulation"], "4096 QAM")
        self.assertEqual(data["top_modulation_rank"], 100)
        # carrier_count defaults to 1 when unset.
        self.assertEqual(data["carrier_count"], 1)

        target_keys = {
            "modulation", "modulation_rank", "data_rate_kbps", "max_power_dbm",
            "eirp_dbm", "expected_rsl_dbm", "warning_margin_db",
            "critical_margin_db", "alarm_enabled",
            "effective_warning_rsl_dbm", "effective_critical_rsl_dbm",
        }
        self.assertEqual(set(data["modulation_targets"][0].keys()), target_keys)

    def test_zabbix_targets_ordered_by_rank_desc(self):
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/{self.profile.pk}/zabbix/"
            f"?direction=A_TO_Z"
        )
        ranks = [t["modulation_rank"] for t in r.json()["modulation_targets"]]
        self.assertEqual(ranks, sorted(ranks, reverse=True))
        self.assertEqual(ranks, [100, 60])

    def test_zabbix_both_directions(self):
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/{self.profile.pk}/zabbix/"
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)
        directions = {d["direction"] for d in data}
        self.assertEqual(directions, {"A_TO_Z", "Z_TO_A"})

    def test_zabbix_applies_global_tolerance(self):
        # Clear seeded band rules so the global default (not a band rule) applies.
        WirelessBandTolerance.objects.all().delete()
        s = WirelessGlobalSettings.load()
        s.global_tolerance_db = Decimal("2")
        s.tolerance_enabled = True
        s.save()
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/{self.profile.pk}/zabbix/"
            f"?direction=A_TO_Z"
        )
        data = r.json()
        self.assertEqual(data["global_tolerance_db"], "2.00")
        self.assertIsNone(data["exception"])
        # Top target = 4096 QAM, expected_rsl -42, warning_margin 3.
        # effective_warning = -42 - (3 + 2) = -47
        top = data["modulation_targets"][0]
        self.assertEqual(top["effective_warning_rsl_dbm"], "-47.000")

    # --- LLM config endpoints (serializers must resolve for change logging) ---

    def test_llm_provider_create(self):
        # Exercises change-log serialization on save (the path that 500'd when the
        # serializer was missing).
        r = self.client.post(
            f"{BASE}/wireless-llm-providers/",
            {"provider": "anthropic", "model": "claude-opus-4-8", "rank": 1},
            format="json",
        )
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(WirelessLLMProvider.objects.count(), 1)

    def test_zabbix_surfaces_active_exception(self):
        WirelessTargetException.objects.create(
            wireless_license_profile=self.profile,
            reason="awaiting tower work",
            suppress_alarms=True,
            enabled=True,
        )
        r = self.client.get(
            f"{BASE}/wireless-license-profiles/{self.profile.pk}/zabbix/"
            f"?direction=A_TO_Z"
        )
        exc = r.json()["exception"]
        self.assertIsNotNone(exc)
        self.assertTrue(exc["active"])
        self.assertTrue(exc["suppress_alarms"])
        self.assertEqual(exc["reason"], "awaiting tower work")
