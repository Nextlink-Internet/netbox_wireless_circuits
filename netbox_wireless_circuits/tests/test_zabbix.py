from decimal import Decimal

from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider
from dcim.models import (
    Device,
    DeviceRole,
    DeviceType,
    Interface,
    Manufacturer,
    Site,
)

from netbox_wireless_circuits.models import (
    WirelessCircuitEndpoint,
    WirelessGlobalSettings,
    WirelessLicenseProfile,
    WirelessModulationTarget,
    WirelessTargetException,
)
from netbox_wireless_circuits.zabbix import (
    RX_DIRECTION_FOR_SIDE,
    device_sync_plan,
    effective_critical_rsl,
    effective_warning_rsl,
    macro_values_for_direction,
    sanitize_prefix,
)


def make_device(tag):
    site = Site.objects.create(name=f"S-{tag}", slug=f"s-{tag.lower()}")
    mfr = Manufacturer.objects.create(name=f"M-{tag}", slug=f"m-{tag.lower()}")
    dt = DeviceType.objects.create(manufacturer=mfr, model=f"DT-{tag}", slug=f"dt-{tag.lower()}")
    role = DeviceRole.objects.create(name=f"R-{tag}", slug=f"r-{tag.lower()}")
    return Device.objects.create(
        name=f"radio-{tag}", device_type=dt, role=role, site=site, status="active"
    )


class ThresholdMathTests(TestCase):
    def test_sanitize_prefix(self):
        self.assertEqual(sanitize_prefix("WL"), "WL")
        self.assertEqual(sanitize_prefix("  {$WL}  "), "WL")
        self.assertEqual(sanitize_prefix(""), "WL")
        self.assertEqual(sanitize_prefix(None), "WL")
        self.assertEqual(sanitize_prefix("MW"), "MW")

    def test_rx_direction_for_side(self):
        # A radio on side Z receives the A->Z direction; side A receives Z->A.
        self.assertEqual(RX_DIRECTION_FOR_SIDE["Z"], "A_TO_Z")
        self.assertEqual(RX_DIRECTION_FOR_SIDE["A"], "Z_TO_A")

    def test_effective_rsl(self):
        t = WirelessModulationTarget(
            expected_rsl_dbm=Decimal("-42"),
            warning_margin_db=Decimal("3"),
            critical_margin_db=Decimal("6"),
        )
        self.assertEqual(effective_warning_rsl(t, Decimal("2")), Decimal("-47"))
        self.assertEqual(effective_critical_rsl(t, Decimal("2")), Decimal("-50"))

    def test_effective_rsl_none_when_no_expected(self):
        t = WirelessModulationTarget(expected_rsl_dbm=None)
        self.assertIsNone(effective_warning_rsl(t, Decimal("0")))


class MacroValueTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(name="Microwave", slug="microwave")
        circuit = Circuit.objects.create(cid="MW-1", provider=provider, type=ctype)
        cls.profile = WirelessLicenseProfile.objects.create(
            circuit=circuit, frequency_band="11 GHz"
        )
        WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile, direction="A_TO_Z",
            modulation="4096 QAM", expected_rsl_dbm=Decimal("-42"),
            warning_margin_db=Decimal("3"), critical_margin_db=Decimal("6"),
            alarm_enabled=True,
        )
        WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile, direction="A_TO_Z",
            modulation="256 QAM", expected_rsl_dbm=Decimal("-60"), alarm_enabled=True,
        )

    def test_macro_values_top_target(self):
        values = macro_values_for_direction(self.profile, "A_TO_Z", Decimal("2"), None)
        self.assertEqual(values["RSL.EXPECTED"], Decimal("-42"))
        self.assertEqual(values["RSL.WARN"], Decimal("-47"))
        self.assertEqual(values["RSL.CRIT"], Decimal("-50"))
        self.assertEqual(values["MOD.TOP"], "4096 QAM")
        self.assertEqual(values["MOD.TOP_RANK"], 100)
        self.assertEqual(values["ALARM.SUPPRESS"], 0)
        self.assertEqual(values["CID"], "MW-1")
        self.assertNotIn("RSL.ADJUSTED", values)

    def test_macro_values_with_active_exception(self):
        exc = WirelessTargetException(
            wireless_license_profile=self.profile, reason="x",
            suppress_alarms=True, adjusted_rsl_dbm=Decimal("-55"), enabled=True,
        )
        values = macro_values_for_direction(self.profile, "A_TO_Z", Decimal("0"), exc)
        self.assertEqual(values["ALARM.SUPPRESS"], 1)
        self.assertEqual(values["RSL.ADJUSTED"], Decimal("-55"))

    def test_macro_values_empty_when_no_enabled_target(self):
        empty = macro_values_for_direction(self.profile, "Z_TO_A", Decimal("0"), None)
        self.assertEqual(empty, {})


class DeviceSyncPlanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(name="Microwave", slug="microwave")
        circuit = Circuit.objects.create(cid="MW-RX", provider=provider, type=ctype)
        cls.profile = WirelessLicenseProfile.objects.create(
            circuit=circuit, frequency_band="11 GHz"
        )
        cls.device = make_device("Z")
        # Device sits on side Z -> it receives the A_TO_Z direction.
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=cls.profile, side="Z", netbox_device=cls.device,
        )
        WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile, direction="A_TO_Z",
            modulation="4096 QAM", expected_rsl_dbm=Decimal("-42"),
            warning_margin_db=Decimal("3"), critical_margin_db=Decimal("6"),
            alarm_enabled=True,
        )

    def test_plan_macros_and_tags(self):
        settings = WirelessGlobalSettings.load()
        settings.zabbix_macro_prefix = "WL"
        settings.zabbix_emit_tags = True
        plan = device_sync_plan(self.device, settings)
        names = {m["name"]: m["value"] for m in plan["macros"]}
        self.assertEqual(names["{$WL.RSL.EXPECTED}"], "-42")
        self.assertEqual(names["{$WL.RSL.WARN}"], "-45")  # tolerance 0 by default
        self.assertEqual(names["{$WL.MOD.TOP}"], "4096 QAM")
        # All single-link macros carry empty context.
        self.assertTrue(all(m["context"] == "" for m in plan["macros"]))
        tags = {(t["tag"], t["value"]) for t in plan["tags"]}
        self.assertIn(("wireless-circuit", "MW-RX"), tags)
        self.assertIn(("wireless-band", "11 GHz"), tags)

    def test_plan_prefix_configurable(self):
        settings = WirelessGlobalSettings.load()
        settings.zabbix_macro_prefix = "MW"
        plan = device_sync_plan(self.device, settings)
        self.assertTrue(any(m["name"] == "{$MW.RSL.WARN}" for m in plan["macros"]))

    def test_plan_multi_radio_uses_context(self):
        # Add a second link on the same device via a different interface.
        iface = Interface.objects.create(device=self.device, name="radio1", type="other")
        WirelessCircuitEndpoint.objects.filter(
            wireless_license_profile=self.profile, side="Z"
        ).update(netbox_interface=iface)

        provider = Provider.objects.get(slug="comsearch")
        ctype = CircuitType.objects.get(slug="microwave")
        circuit2 = Circuit.objects.create(cid="MW-RX2", provider=provider, type=ctype)
        profile2 = WirelessLicenseProfile.objects.create(circuit=circuit2)
        iface2 = Interface.objects.create(device=self.device, name="radio2", type="other")
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=profile2, side="Z",
            netbox_device=self.device, netbox_interface=iface2,
        )
        WirelessModulationTarget.objects.create(
            wireless_license_profile=profile2, direction="A_TO_Z",
            modulation="256 QAM", expected_rsl_dbm=Decimal("-50"), alarm_enabled=True,
        )

        settings = WirelessGlobalSettings.load()
        plan = device_sync_plan(self.device, settings)
        contexts = {m["context"] for m in plan["macros"]}
        self.assertEqual(contexts, {"radio1", "radio2"})
