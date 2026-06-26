import django_tables2 as tables

from netbox.tables import NetBoxTable, columns

from .models import (
    WirelessAntenna,
    WirelessBandTolerance,
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessLLMProvider,
    WirelessModulationTarget,
    WirelessTargetException,
)


class WirelessLicenseProfileTable(NetBoxTable):
    circuit = tables.Column(linkify=True)
    registration_status = columns.ChoiceFieldColumn(verbose_name="License status")
    license_expiration = tables.DateColumn(
        accessor="license_expiration", verbose_name="License expires", orderable=False,
    )
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
            "license_expiration",
            "pcn_number",
            "rcn_number",
            "job_number",
            "licensee",
            "call_sign",
            "channel_plan_mhz",
            "radio_configuration",
            "carrier_count",
            "receiver_threshold_dbm",
            "created",
            "last_updated",
        )
        default_columns = (
            "circuit",
            "frequency_band",
            "registration_status",
            "license_expiration",
            "rcn_number",
            "licensee",
        )


class WirelessCircuitEndpointTable(NetBoxTable):
    wireless_license_profile = tables.Column(linkify=True)
    side = columns.ChoiceFieldColumn()
    netbox_site = tables.Column(linkify=True)
    netbox_device = tables.Column(linkify=True)
    netbox_interface = tables.Column(linkify=True)
    license_status = columns.ChoiceFieldColumn()

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
            "license_status",
            "license_basis",
            "license_expiration_date",
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
            "license_status",
            "license_expiration_date",
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


class WirelessBandToleranceTable(NetBoxTable):
    frequency_band = columns.ChoiceFieldColumn(linkify=True)
    enabled = columns.BooleanColumn()

    class Meta(NetBoxTable.Meta):
        model = WirelessBandTolerance
        fields = (
            "pk", "id", "frequency_band", "tolerance_db", "enabled",
            "created", "last_updated",
        )
        default_columns = ("frequency_band", "tolerance_db", "enabled")
        order_by = ("frequency_band",)


class WirelessAntennaTable(NetBoxTable):
    antenna_code = tables.Column(linkify=True)
    manufacturer = tables.Column()

    class Meta(NetBoxTable.Meta):
        model = WirelessAntenna
        fields = (
            "pk", "id", "manufacturer", "antenna_code", "model",
            "diameter_ft", "diameter_m", "gain_dbi", "beamwidth_deg",
            "polarization", "frequency_range",
            "created", "last_updated",
        )
        default_columns = (
            "manufacturer", "antenna_code", "model", "diameter_ft",
            "gain_dbi", "beamwidth_deg",
        )
        order_by = ("manufacturer", "antenna_code")


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
