from django.test import TestCase

from circuits.models import Circuit, CircuitType, Provider
from dcim.models import Interface, Site
from utilities.testing import create_test_device

from netbox_wireless_circuits.filtersets import (
    WirelessLicenseProfileFilterSet,
    WirelessModulationTargetFilterSet,
)
from netbox_wireless_circuits.models import (
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessModulationTarget,
)


class WirelessLicenseProfileFilterSetTests(TestCase):
    queryset = WirelessLicenseProfile.objects.all()
    filterset = WirelessLicenseProfileFilterSet

    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(
            name="Licensed Microwave", slug="licensed-microwave"
        )
        cls.c1 = Circuit.objects.create(cid="MW-TX-STILES-001", provider=provider, type=ctype)
        cls.c2 = Circuit.objects.create(cid="MW-OK-TULSA-002", provider=provider, type=ctype)

        cls.p1 = WirelessLicenseProfile.objects.create(
            circuit=cls.c1, frequency_band="11 GHz", registration_status="licensed"
        )
        cls.p2 = WirelessLicenseProfile.objects.create(
            circuit=cls.c2, frequency_band="23 GHz", registration_status="applied"
        )

        cls.site = Site.objects.create(name="Stiles", slug="stiles")
        cls.device = create_test_device("radio-stiles")
        cls.iface = Interface.objects.create(
            device=cls.device, name="radio0", type="other"
        )
        WirelessCircuitEndpoint.objects.create(
            wireless_license_profile=cls.p1,
            side="A",
            netbox_site=cls.site,
            netbox_device=cls.device,
            netbox_interface=cls.iface,
        )

    def _qs(self, params):
        return self.filterset(params, self.queryset).qs

    def test_filter_by_circuit_id(self):
        self.assertEqual(list(self._qs({"circuit_id": [self.c1.pk]})), [self.p1])

    def test_filter_by_circuit_cid(self):
        self.assertEqual(list(self._qs({"circuit_cid": "STILES"})), [self.p1])

    def test_filter_by_band(self):
        self.assertEqual(list(self._qs({"frequency_band": ["11 GHz"]})), [self.p1])

    def test_filter_by_registration_status(self):
        self.assertEqual(
            list(self._qs({"registration_status": ["applied"]})), [self.p2]
        )

    def test_filter_by_site(self):
        self.assertEqual(list(self._qs({"site": [self.site.pk]})), [self.p1])

    def test_filter_by_device(self):
        self.assertEqual(list(self._qs({"device": [self.device.pk]})), [self.p1])

    def test_filter_by_interface(self):
        self.assertEqual(list(self._qs({"interface": [self.iface.pk]})), [self.p1])


class WirelessModulationTargetFilterSetTests(TestCase):
    queryset = WirelessModulationTarget.objects.all()
    filterset = WirelessModulationTargetFilterSet

    @classmethod
    def setUpTestData(cls):
        provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        ctype = CircuitType.objects.create(
            name="Licensed Microwave", slug="licensed-microwave"
        )
        cls.circuit = Circuit.objects.create(
            cid="MW-TX-STILES-001", provider=provider, type=ctype
        )
        cls.profile = WirelessLicenseProfile.objects.create(circuit=cls.circuit)

        cls.t_az = WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile,
            direction="A_TO_Z",
            modulation="256 QAM",
            alarm_enabled=True,
        )
        cls.t_za = WirelessModulationTarget.objects.create(
            wireless_license_profile=cls.profile,
            direction="Z_TO_A",
            modulation="64 QAM",
            alarm_enabled=False,
        )

    def _qs(self, params):
        return self.filterset(params, self.queryset).qs

    def test_filter_by_direction(self):
        self.assertEqual(list(self._qs({"direction": ["A_TO_Z"]})), [self.t_az])

    def test_filter_by_alarm_enabled(self):
        self.assertEqual(list(self._qs({"alarm_enabled": True})), [self.t_az])
        self.assertEqual(list(self._qs({"alarm_enabled": False})), [self.t_za])

    def test_filter_by_circuit_cid(self):
        qs = self._qs({"circuit_cid": "STILES"})
        self.assertEqual(qs.count(), 2)
