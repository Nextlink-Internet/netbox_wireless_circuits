from django import forms

from circuits.models import Circuit
from dcim.models import Device, Interface, Site
from netbox.forms import NetBoxModelForm, NetBoxModelImportForm
from utilities.forms.fields import CSVChoiceField, CSVModelChoiceField, DynamicModelChoiceField

from .choices import FrequencyBandChoices, ModulationChoices, ModulationDirectionChoices
from .models import (
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
    "WirelessTargetExceptionForm",
    "WirelessLLMSettingsForm",
    "WirelessLLMProviderForm",
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
