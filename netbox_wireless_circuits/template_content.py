from netbox.plugins import PluginTemplateExtension

from .models import WirelessLicenseProfile


class CircuitWirelessLicensePanel(PluginTemplateExtension):
    """Adds a compact 'Wireless License' summary panel to the Circuit detail page."""

    # NetBox 4.5 uses the plural ``models`` attribute (list of "<app>.<model>").
    models = ["circuits.circuit"]

    def right_page(self):
        circuit = self.context["object"]
        try:
            profile = circuit.wireless_license_profile
        except WirelessLicenseProfile.DoesNotExist:
            profile = None

        return self.render(
            "netbox_wireless_circuits/circuit_wireless_panel.html",
            extra_context={"profile": profile, "circuit": circuit},
        )


template_extensions = [CircuitWirelessLicensePanel]
