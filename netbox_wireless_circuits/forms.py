from django import forms

from circuits.choices import CircuitStatusChoices
from circuits.models import Circuit, CircuitType, Provider
from dcim.models import Device, Interface, Site
from netbox.forms import NetBoxModelForm, NetBoxModelImportForm
from utilities.forms.fields import CSVChoiceField, CSVModelChoiceField, DynamicModelChoiceField

from .choices import FrequencyBandChoices, ModulationChoices, ModulationDirectionChoices
from .models import (
    WirelessAntenna,
    WirelessBandTolerance,
    WirelessCircuitEndpoint,
    WirelessGlobalSettings,
    WirelessLicenseProfile,
    WirelessLLMProvider,
    WirelessLLMSettings,
    WirelessModulationTarget,
    WirelessTargetException,
)

__all__ = (
    "WirelessLicenseProfileForm",
    "WirelessCircuitEndpointForm",
    "WirelessModulationTargetForm",
    "WirelessGlobalSettingsForm",
    "WirelessBandToleranceForm",
    "WirelessAntennaForm",
    "WirelessTargetExceptionForm",
    "WirelessLLMSettingsForm",
    "WirelessLLMProviderForm",
    "WirelessPCNUploadForm",
    "WirelessPCNConfirmForm",
    "WirelessCSVImportForm",
    "WirelessLicenseProfileImportForm",
    "WirelessModulationTargetImportForm",
)


# ---------------------------------------------------------------------------
# Edit forms
# ---------------------------------------------------------------------------

class WirelessLicenseProfileForm(NetBoxModelForm):
    circuit = DynamicModelChoiceField(queryset=Circuit.objects.all())

    class Meta:
        model = WirelessLicenseProfile
        fields = (
            "circuit",
            "pcn_date",
            "job_number",
            "pcn_number",
            "rcn_number",
            "registration_status",
            "registration_date",
            "registration_completion_date",
            "licensee",
            "call_sign",
            "radio_service",
            "station_class",
            "frequency_band",
            "channel_plan_mhz",
            "carrier_count",
            "radio_configuration",
            "path_length_km",
            "path_length_miles",
            "atmospheric_loss_db",
            "free_space_loss_db",
            "receiver_threshold_dbm",
            "source_document",
            "notes",
            "tags",
        )


class WirelessCircuitEndpointForm(NetBoxModelForm):
    wireless_license_profile = DynamicModelChoiceField(
        queryset=WirelessLicenseProfile.objects.all(),
    )
    netbox_site = DynamicModelChoiceField(
        queryset=Site.objects.all(),
        required=False,
        label="Site",
    )
    netbox_device = DynamicModelChoiceField(
        queryset=Device.objects.all(),
        required=False,
        label="Device",
        query_params={"site_id": "$netbox_site"},
    )
    netbox_interface = DynamicModelChoiceField(
        queryset=Interface.objects.all(),
        required=False,
        label="Interface",
        query_params={"device_id": "$netbox_device"},
    )
    antenna = DynamicModelChoiceField(
        queryset=WirelessAntenna.objects.all(),
        required=False,
        label="Antenna (catalog)",
    )

    class Meta:
        model = WirelessCircuitEndpoint
        fields = (
            "wireless_license_profile",
            "side",
            "netbox_site",
            "netbox_device",
            "netbox_interface",
            "pcn_site_name",
            "county_state",
            "latitude",
            "longitude",
            "ground_elevation_m",
            "ground_elevation_ft",
            "asr_number",
            "structure_height_agl_m",
            "structure_height_agl_ft",
            "path_azimuth_deg",
            "antenna",
            "antenna_code",
            "antenna_manufacturer",
            "antenna_model",
            "antenna_diameter_ft",
            "antenna_gain_dbi",
            "antenna_beamwidth_deg",
            "antenna_tilt_deg",
            "centerline_agl_m",
            "centerline_agl_ft",
            "transmit_mode",
            "radio_code",
            "radio_manufacturer",
            "radio_model",
            "radio_description",
            "stability_percent",
            "nominal_power_dbm",
            "nominal_rsl_dbm",
            "coordinated_power_dbm",
            "coordinated_rsl_dbm",
            "maximum_power_dbm",
            "maximum_rsl_dbm",
            "fixed_loss_common_db",
            "fixed_loss_tx_db",
            "fixed_loss_rx_db",
            "tx_frequency_mhz",
            "polarization",
            "tags",
        )


class WirelessModulationTargetForm(NetBoxModelForm):
    wireless_license_profile = DynamicModelChoiceField(
        queryset=WirelessLicenseProfile.objects.all(),
    )

    class Meta:
        model = WirelessModulationTarget
        fields = (
            "wireless_license_profile",
            "direction",
            "modulation",
            "modulation_rank",
            "radio_model",
            "emission_designator",
            "data_rate_kbps",
            "max_power_dbm",
            "eirp_dbm",
            "expected_rsl_dbm",
            "min_acceptable_rsl_dbm",
            "max_acceptable_rsl_dbm",
            "warning_margin_db",
            "critical_margin_db",
            "alarm_enabled",
            "notes",
            "tags",
        )
        help_texts = {
            "modulation_rank": "Leave blank to auto-fill from the canonical rank map.",
        }


class WirelessGlobalSettingsForm(NetBoxModelForm):
    class Meta:
        model = WirelessGlobalSettings
        fields = (
            "global_tolerance_db",
            "tolerance_enabled",
            "zabbix_sync_enabled",
            "zabbix_macro_prefix",
            "zabbix_emit_tags",
            "link_type_tag_enabled",
            "link_type_tag_template",
            "notes",
            "tags",
        )


class WirelessLLMSettingsForm(NetBoxModelForm):
    class Meta:
        model = WirelessLLMSettings
        fields = (
            "pdf_import_enabled",
            "prompt_override",
            "notes",
            "tags",
        )


class WirelessLLMProviderForm(NetBoxModelForm):
    class Meta:
        model = WirelessLLMProvider
        fields = (
            "rank",
            "provider",
            "model",
            "enabled",
            "notes",
            "tags",
        )


class WirelessBandToleranceForm(NetBoxModelForm):
    class Meta:
        model = WirelessBandTolerance
        fields = (
            "frequency_band",
            "tolerance_db",
            "enabled",
            "notes",
            "tags",
        )


class WirelessAntennaForm(NetBoxModelForm):
    class Meta:
        model = WirelessAntenna
        fields = (
            "manufacturer",
            "antenna_code",
            "model",
            "diameter_ft",
            "diameter_m",
            "gain_dbi",
            "beamwidth_deg",
            "polarization",
            "frequency_range",
            "notes",
            "tags",
        )


class WirelessTargetExceptionForm(NetBoxModelForm):
    wireless_license_profile = DynamicModelChoiceField(
        queryset=WirelessLicenseProfile.objects.all(),
    )

    class Meta:
        model = WirelessTargetException
        fields = (
            "wireless_license_profile",
            "reason",
            "effective_date",
            "expiry_date",
            "adjusted_rsl_dbm",
            "suppress_alarms",
            "enabled",
            "notes",
            "tags",
        )
        # approved_by is set automatically by the view to the acting user.


# ---------------------------------------------------------------------------
# PCN PDF import (LLM-assisted, with manual mapping fallback)
# ---------------------------------------------------------------------------

class WirelessPCNUploadForm(forms.Form):
    pdf = forms.FileField(
        label="PCN PDF",
        help_text="The PCN document to extract licensed values from. A new "
                  "circuit is created from it in the next step.",
    )


def pcn_site_field_key(pidx, eidx):
    """Stable form-field name for one path's one endpoint Site dropdown."""
    return f"site_p{pidx}_e{eidx}"


def pcn_device_field_key(pidx, eidx):
    return f"device_p{pidx}_e{eidx}"


def pcn_interface_field_key(pidx, eidx):
    return f"iface_p{pidx}_e{eidx}"


class WirelessPCNConfirmForm(forms.Form):
    """
    Step 2: choose the shared provider/type, optionally assign each side of each
    path to a NetBox site, and review/edit the extracted data (manual mapping)
    before the circuits are created. A PCN PDF may contain several paths; each
    becomes its own circuit and carries its own ``cid``.

    The per-side Site fields are built dynamically from ``endpoint_specs`` (the
    number of paths/endpoints is only known after extraction); the view passes
    the same specs when rendering and when handling the submit so the bound
    fields line up.
    """

    provider = DynamicModelChoiceField(
        queryset=Provider.objects.all(), label="Provider",
        help_text="Provider / licensing context applied to every path's circuit.",
    )
    circuit_type = DynamicModelChoiceField(
        queryset=CircuitType.objects.all(), label="Circuit type",
        help_text="Circuit type applied to every path's circuit.",
    )
    data_json = forms.CharField(
        label="Extracted paths",
        widget=forms.Textarea(attrs={"rows": 26, "class": "form-control font-monospace"}),
        help_text="One entry per path under \"paths\". Set each path's \"cid\" and "
                  "correct any values; keys: cid, profile, endpoints[], "
                  "modulation_targets[].",
    )

    def __init__(self, *args, endpoint_specs=None, **kwargs):
        super().__init__(*args, **kwargs)
        # One row of (Site, Device, Interface) dropdowns per endpoint, built
        # dynamically (the path/endpoint count is only known after extraction).
        # Device is filtered by the chosen Site, Interface by the chosen Device.
        self._endpoint_rows = []
        for spec in (endpoint_specs or []):
            pidx, eidx = spec["pidx"], spec["eidx"]
            site_key = pcn_site_field_key(pidx, eidx)
            device_key = pcn_device_field_key(pidx, eidx)
            iface_key = pcn_interface_field_key(pidx, eidx)
            self.fields[site_key] = DynamicModelChoiceField(
                queryset=Site.objects.all(), required=False, label="Site",
                initial=spec.get("initial"),
                help_text="Optional — link this side to a NetBox site.",
            )
            self.fields[device_key] = DynamicModelChoiceField(
                queryset=Device.objects.all(), required=False, label="Radio device",
                query_params={"site_id": f"${site_key}"},
                help_text="Optional — the radio's NetBox device.",
            )
            self.fields[iface_key] = DynamicModelChoiceField(
                queryset=Interface.objects.all(), required=False, label="Interface",
                query_params={"device_id": f"${device_key}"},
            )
            self._endpoint_rows.append({
                "label": spec["label"], "pidx": pidx, "eidx": eidx,
                "site_key": site_key, "device_key": device_key, "iface_key": iface_key,
            })

    @property
    def endpoint_rows(self):
        """Bound (label, site, device, interface) field rows for the template."""
        return [
            {
                "label": r["label"],
                "site": self[r["site_key"]],
                "device": self[r["device_key"]],
                "interface": self[r["iface_key"]],
            }
            for r in self._endpoint_rows
        ]

    def endpoint_assignments(self):
        """
        Yield ``(pidx, eidx, {netbox_site, netbox_device, netbox_interface})`` for
        every endpoint where the operator chose at least one object.
        """
        for r in self._endpoint_rows:
            chosen = {}
            site = self.cleaned_data.get(r["site_key"])
            device = self.cleaned_data.get(r["device_key"])
            interface = self.cleaned_data.get(r["iface_key"])
            if site:
                chosen["netbox_site"] = site
            if device:
                chosen["netbox_device"] = device
            if interface:
                chosen["netbox_interface"] = interface
            if chosen:
                yield r["pidx"], r["eidx"], chosen

    def clean_data_json(self):
        import json

        try:
            data = json.loads(self.cleaned_data["data_json"])
        except json.JSONDecodeError as exc:
            raise forms.ValidationError(f"Invalid JSON: {exc}")
        if not isinstance(data, dict):
            raise forms.ValidationError("Top-level value must be a JSON object.")
        return data


# ---------------------------------------------------------------------------
# Source-aware bulk CSV import (Comsearch & future coordinators)
# ---------------------------------------------------------------------------

class WirelessCSVImportForm(forms.Form):
    """
    Bulk-import a coordinator's CSV export. The operator picks the data source
    (each has its own column layout), the provider / circuit type / status applied
    to every created circuit, and uploads the file. The import runs as a background
    job; existing links are reported, not modified.
    """

    source = forms.ChoiceField(
        label="Data source",
        help_text="Which coordinator export this CSV is. Each source maps its own "
                  "columns and de-duplicates on its own stable per-link key.",
    )
    file = forms.FileField(
        label="CSV file",
        help_text="The coordinator export to import.",
    )
    provider = DynamicModelChoiceField(
        queryset=Provider.objects.all(), label="Provider",
        help_text="Provider / licensing context applied to every created circuit.",
    )
    circuit_type = DynamicModelChoiceField(
        queryset=CircuitType.objects.all(), label="Circuit type",
        help_text="Circuit type applied to every created circuit.",
    )
    status = forms.ChoiceField(
        choices=CircuitStatusChoices, initial="active", label="Circuit status",
        help_text="Native circuit status applied to every created circuit.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .importers import all_sources
        self.fields["source"].choices = [(s.name, s.label) for s in all_sources()]


# ---------------------------------------------------------------------------
# CSV import forms
# ---------------------------------------------------------------------------

class WirelessLicenseProfileImportForm(NetBoxModelImportForm):
    cid = CSVModelChoiceField(
        queryset=Circuit.objects.all(),
        to_field_name="cid",
        help_text="Circuit ID (CID) of an existing native NetBox circuit",
    )
    band = CSVChoiceField(
        choices=FrequencyBandChoices,
        required=False,
        help_text="Frequency band",
    )
    atmospheric_loss = forms.DecimalField(
        required=False, help_text="Atmospheric loss (dB)",
    )
    free_space_loss = forms.DecimalField(
        required=False, help_text="Free space loss (dB)",
    )
    receiver_threshold = forms.DecimalField(
        required=False, help_text="Receiver threshold (dBm)",
    )

    class Meta:
        model = WirelessLicenseProfile
        fields = (
            "cid",
            "pcn_date",
            "job_number",
            "rcn_number",
            "band",
            "channel_plan_mhz",
            "path_length_km",
            "path_length_miles",
            "atmospheric_loss",
            "free_space_loss",
            "receiver_threshold",
            "licensee",
            "call_sign",
            "radio_service",
            "station_class",
        )

    def clean(self):
        super().clean()
        # Map CSV column names onto the underlying model fields so the base
        # import form's save() (custom fields, tags, etc.) runs unchanged.
        if self.cleaned_data.get("cid"):
            self.instance.circuit = self.cleaned_data["cid"]
        if self.cleaned_data.get("band"):
            self.instance.frequency_band = self.cleaned_data["band"]
        if self.cleaned_data.get("atmospheric_loss") is not None:
            self.instance.atmospheric_loss_db = self.cleaned_data["atmospheric_loss"]
        if self.cleaned_data.get("free_space_loss") is not None:
            self.instance.free_space_loss_db = self.cleaned_data["free_space_loss"]
        if self.cleaned_data.get("receiver_threshold") is not None:
            self.instance.receiver_threshold_dbm = self.cleaned_data["receiver_threshold"]
        return self.cleaned_data


class WirelessModulationTargetImportForm(NetBoxModelImportForm):
    cid = CSVModelChoiceField(
        queryset=Circuit.objects.all(),
        to_field_name="cid",
        help_text="Circuit ID (CID); resolved to its wireless license profile",
    )
    direction = CSVChoiceField(
        choices=ModulationDirectionChoices,
        help_text="A_TO_Z or Z_TO_A",
    )
    modulation = CSVChoiceField(
        choices=ModulationChoices,
        help_text="Modulation (e.g. 256 QAM)",
    )

    class Meta:
        model = WirelessModulationTarget
        fields = (
            "cid",
            "direction",
            "modulation",
            "modulation_rank",
            "data_rate_kbps",
            "max_power_dbm",
            "eirp_dbm",
            "expected_rsl_dbm",
            "emission_designator",
            "radio_model",
        )

    def clean(self):
        super().clean()
        circuit = self.cleaned_data.get("cid")
        if circuit:
            profile = WirelessLicenseProfile.objects.filter(circuit=circuit).first()
            if profile is None:
                raise forms.ValidationError(
                    f"Circuit '{circuit.cid}' has no wireless license profile. "
                    f"Create the profile before importing modulation targets."
                )
            self.instance.wireless_license_profile = profile
        return self.cleaned_data
