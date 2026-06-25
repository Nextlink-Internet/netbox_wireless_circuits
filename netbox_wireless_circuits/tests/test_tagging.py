from django.test import SimpleTestCase, TestCase

from circuits.models import Circuit, CircuitType, Provider

from netbox_wireless_circuits.models import (
    WirelessGlobalSettings,
    WirelessLicenseProfile,
)
from netbox_wireless_circuits.tagging import (
    apply_link_type_tag,
    tag_name,
)


class TagNameTests(SimpleTestCase):
    def test_default_template(self):
        self.assertEqual(tag_name("link_type: {config}", "2+0"), "link_type: 2+0")

    def test_value_only(self):
        self.assertEqual(tag_name("{config}", "4+0"), "4+0")

    def test_custom_prefix(self):
        self.assertEqual(tag_name("MW-{config}", "1+0"), "MW-1+0")


class ApplyLinkTypeTagTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.provider = Provider.objects.create(name="Comsearch", slug="comsearch")
        cls.ctype = CircuitType.objects.create(name="Microwave", slug="microwave")

    def _settings(self, enabled=True, template="link_type: {config}"):
        s = WirelessGlobalSettings.load()
        s.link_type_tag_enabled = enabled
        s.link_type_tag_template = template
        s.save()
        return s

    def _profile(self, cid, config):
        circuit = Circuit.objects.create(cid=cid, provider=self.provider, type=self.ctype)
        # post_save signal already applies the tag; return both for assertions.
        profile = WirelessLicenseProfile.objects.create(
            circuit=circuit, radio_configuration=config
        )
        return circuit, profile

    def test_applies_tag_on_create(self):
        self._settings()
        circuit, _ = self._profile("LT-1", "2+0")
        names = {t.name for t in circuit.tags.all()}
        self.assertIn("link_type: 2+0", names)

    def test_disabled_applies_nothing(self):
        self._settings(enabled=False)
        circuit, _ = self._profile("LT-2", "2+0")
        self.assertEqual(circuit.tags.count(), 0)

    def test_changing_config_replaces_stale_tag(self):
        self._settings()
        circuit, profile = self._profile("LT-3", "2+0")
        self.assertIn("link_type: 2+0", {t.name for t in circuit.tags.all()})
        profile.radio_configuration = "4+0"
        profile.save()
        names = {t.name for t in circuit.tags.all()}
        self.assertIn("link_type: 4+0", names)
        self.assertNotIn("link_type: 2+0", names)  # stale removed

    def test_no_config_applies_nothing(self):
        self._settings()
        circuit, _ = self._profile("LT-4", "")
        self.assertEqual(circuit.tags.count(), 0)
