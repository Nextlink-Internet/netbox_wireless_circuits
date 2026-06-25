import django_tables2 as tables

from netbox.tables import NetBoxTable, columns

from .models import (
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessLLMProvider,
    WirelessModulationTarget,
    WirelessTargetException,
)


class WirelessLicenseProfileTable(NetBoxTable):
    circuit = tables.Column(linkify=True)
    registration_status = columns.ChoiceFieldColumn()
    frequency_band = tables.Column()
    pcn_number = tables.Column()
    rcn_number = tables.Column()
    licensee = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = WirelessLicenseProfile
        fields = (
            "pk",
            "id",
            "circuit",
            "frequency_band",
            "registration_status",
            "pcn_number",
            "rcn_number",
            "job_number",
            "licensee",
            "call_sign",
            "channel_plan_mhz",
            "receiver_threshold_dbm",
            "created",
            "last_updated",
        )
        default_columns = (
            "circuit",
            "frequency_band",
            "registration_status",
            "pcn_number",
            "rcn_number",
            "licensee",
        )


class WirelessCircuitEndpointTable(NetBoxTable):
    wireless_license_profile = tables.Column(linkify=True)
    side = columns.ChoiceFieldColumn()
    netbox_site = tables.Column(linkify=True)
    netbox_device = tables.Column(linkify=True)
    netbox_interface = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = WirelessCircuitEndpoint
        fields = (
            "pk",
            "id",
            "wireless_license_profile",
            "side",
            "pcn_site_name",
            "netbox_site",
            "netbox_device",
            "netbox_interface",
            "tx_frequency_mhz",
            "antenna_model",
            "radio_model",
            "polarization",
            "created",
            "last_updated",
        )
        default_columns = (
            "wireless_license_profile",
            "side",
            "pcn_site_name",
            "netbox_site",
            "netbox_device",
            "tx_frequency_mhz",
        )


class WirelessModulationTargetTable(NetBoxTable):
    wireless_license_profile = tables.Column(linkify=True)
    direction = columns.ChoiceFieldColumn()
    modulation = columns.ChoiceFieldColumn()
    alarm_enabled = columns.BooleanColumn()

    class Meta(NetBoxTable.Meta):
        model = WirelessModulationTarget
        fields = (
            "pk",
            "id",
            "wireless_license_profile",
            "direction",
            "modulation",
            "modulation_rank",
            "data_rate_kbps",
            "max_power_dbm",
            "eirp_dbm",
            "expected_rsl_dbm",
            "min_acceptable_rsl_dbm",
            "max_acceptable_rsl_dbm",
            "warning_margin_db",
            "critical_margin_db",
            "alarm_enabled",
            "radio_model",
            "emission_designator",
            "created",
            "last_updated",
        )
        default_columns = (
            "wireless_license_profile",
            "direction",
            "modulation",
            "modulation_rank",
            "expected_rsl_dbm",
            "alarm_enabled",
        )


class WirelessLLMProviderTable(NetBoxTable):
    provider = columns.ChoiceFieldColumn()
    model = tables.Column(linkify=True)
    enabled = columns.BooleanColumn()

    class Meta(NetBoxTable.Meta):
        model = WirelessLLMProvider
        fields = (
            "pk",
            "id",
            "rank",
            "provider",
            "model",
            "enabled",
            "created",
            "last_updated",
        )
        default_columns = ("rank", "provider", "model", "enabled")
        order_by = ("rank",)


class WirelessTargetExceptionTable(NetBoxTable):
    wireless_license_profile = tables.Column(linkify=True)
    approved_by = tables.Column()
    suppress_alarms = columns.BooleanColumn()
    enabled = columns.BooleanColumn()

    class Meta(NetBoxTable.Meta):
        model = WirelessTargetException
        fields = (
            "pk",
            "id",
            "wireless_license_profile",
            "reason",
            "approved_by",
            "effective_date",
            "expiry_date",
            "adjusted_rsl_dbm",
            "suppress_alarms",
            "enabled",
            "created",
            "last_updated",
        )
        default_columns = (
            "wireless_license_profile",
            "approved_by",
            "effective_date",
            "expiry_date",
            "suppress_alarms",
            "enabled",
        )
