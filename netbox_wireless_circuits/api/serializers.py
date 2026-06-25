from rest_framework import serializers

from circuits.api.serializers import CircuitSerializer
from netbox.api.serializers import NetBoxModelSerializer

from ..models import (
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
    "WirelessLicenseProfileSerializer",
    "WirelessCircuitEndpointSerializer",
    "WirelessModulationTargetSerializer",
    "WirelessGlobalSettingsSerializer",
    "WirelessBandToleranceSerializer",
    "WirelessTargetExceptionSerializer",
    "WirelessLLMSettingsSerializer",
    "WirelessLLMProviderSerializer",
)


class WirelessCircuitEndpointSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessCircuitEndpoint
        fields = (
            "id", "url", "display", "wireless_license_profile", "side",
            "netbox_site", "netbox_device", "netbox_interface",
            "pcn_site_name", "county_state", "latitude", "longitude",
            "ground_elevation_m", "ground_elevation_ft", "asr_number",
            "structure_height_agl_m", "structure_height_agl_ft",
            "path_azimuth_deg", "antenna_code", "antenna_manufacturer",
            "antenna_model", "antenna_diameter_ft", "antenna_gain_dbi",
            "antenna_beamwidth_deg", "antenna_tilt_deg",
            "centerline_agl_m", "centerline_agl_ft",
            "transmit_mode", "radio_code", "radio_manufacturer",
            "radio_model", "radio_description", "stability_percent",
            "nominal_power_dbm", "nominal_rsl_dbm",
            "coordinated_power_dbm", "coordinated_rsl_dbm",
            "maximum_power_dbm", "maximum_rsl_dbm",
            "fixed_loss_common_db", "fixed_loss_tx_db", "fixed_loss_rx_db",
            "tx_frequency_mhz", "polarization",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "side", "pcn_site_name")


class WirelessModulationTargetSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessModulationTarget
        fields = (
            "id", "url", "display", "wireless_license_profile",
            "direction", "modulation", "modulation_rank",
            "radio_model", "emission_designator", "data_rate_kbps",
            "max_power_dbm", "eirp_dbm", "expected_rsl_dbm",
            "min_acceptable_rsl_dbm", "max_acceptable_rsl_dbm",
            "warning_margin_db", "critical_margin_db", "alarm_enabled",
            "notes", "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "direction", "modulation", "modulation_rank",
        )


class WirelessGlobalSettingsSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessGlobalSettings
        fields = (
            "id", "url", "display", "global_tolerance_db", "tolerance_enabled",
            "zabbix_sync_enabled", "zabbix_macro_prefix", "zabbix_emit_tags",
            "notes", "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "global_tolerance_db")


class WirelessBandToleranceSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessBandTolerance
        fields = (
            "id", "url", "display", "frequency_band", "tolerance_db", "enabled",
            "notes", "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "frequency_band", "tolerance_db")


class WirelessLLMSettingsSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessLLMSettings
        fields = (
            "id", "url", "display", "pdf_import_enabled", "prompt_override",
            "notes", "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "pdf_import_enabled")


class WirelessLLMProviderSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessLLMProvider
        fields = (
            "id", "url", "display", "rank", "provider", "model", "enabled",
            "notes", "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "rank", "provider", "model")


class WirelessTargetExceptionSerializer(NetBoxModelSerializer):
    class Meta:
        model = WirelessTargetException
        fields = (
            "id", "url", "display", "wireless_license_profile", "reason",
            "approved_by", "effective_date", "expiry_date", "adjusted_rsl_dbm",
            "suppress_alarms", "enabled", "notes",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = (
            "id", "url", "display", "wireless_license_profile", "enabled",
            "suppress_alarms",
        )


class WirelessLicenseProfileSerializer(NetBoxModelSerializer):
    circuit = CircuitSerializer(nested=True)
    endpoints = WirelessCircuitEndpointSerializer(
        nested=True, many=True, read_only=True,
    )
    modulation_targets = WirelessModulationTargetSerializer(
        nested=True, many=True, read_only=True,
    )

    class Meta:
        model = WirelessLicenseProfile
        fields = (
            "id", "url", "display", "circuit",
            "pcn_date", "job_number", "pcn_number", "rcn_number",
            "registration_status", "registration_date",
            "registration_completion_date", "licensee", "call_sign",
            "radio_service", "station_class", "frequency_band",
            "channel_plan_mhz", "path_length_km", "path_length_miles",
            "atmospheric_loss_db", "free_space_loss_db",
            "receiver_threshold_dbm", "source_document", "notes",
            "endpoints", "modulation_targets",
            "tags", "custom_fields", "created", "last_updated",
        )
        brief_fields = ("id", "url", "display", "circuit", "frequency_band")
