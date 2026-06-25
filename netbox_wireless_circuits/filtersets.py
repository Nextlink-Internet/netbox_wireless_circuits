import django_filters
from django.db.models import Q

from circuits.models import Circuit
from dcim.models import Device, Interface, Site
from netbox.filtersets import NetBoxModelFilterSet

from .choices import (
    EndpointSideChoices,
    FrequencyBandChoices,
    ModulationChoices,
    ModulationDirectionChoices,
    RegistrationStatusChoices,
)
from .models import (
    WirelessCircuitEndpoint,
    WirelessLicenseProfile,
    WirelessModulationTarget,
    WirelessTargetException,
)

__all__ = (
    "WirelessLicenseProfileFilterSet",
    "WirelessCircuitEndpointFilterSet",
    "WirelessModulationTargetFilterSet",
    "WirelessTargetExceptionFilterSet",
)


class WirelessLicenseProfileFilterSet(NetBoxModelFilterSet):
    circuit_id = django_filters.ModelMultipleChoiceFilter(
        field_name="circuit",
        queryset=Circuit.objects.all(),
        label="Circuit (ID)",
    )
    circuit_cid = django_filters.CharFilter(
        method="filter_circuit_cid",
        label="Circuit CID (contains)",
    )
    frequency_band = django_filters.MultipleChoiceFilter(
        choices=FrequencyBandChoices,
    )
    registration_status = django_filters.MultipleChoiceFilter(
        choices=RegistrationStatusChoices,
    )
    site = django_filters.ModelMultipleChoiceFilter(
        field_name="endpoints__netbox_site",
        queryset=Site.objects.all(),
        distinct=True,
        label="Site (via endpoint)",
    )
    device = django_filters.ModelMultipleChoiceFilter(
        field_name="endpoints__netbox_device",
        queryset=Device.objects.all(),
        distinct=True,
        label="Device (via endpoint)",
    )
    interface = django_filters.ModelMultipleChoiceFilter(
        field_name="endpoints__netbox_interface",
        queryset=Interface.objects.all(),
        distinct=True,
        label="Interface (via endpoint)",
    )

    class Meta:
        model = WirelessLicenseProfile
        fields = (
            "id",
            "circuit",
            "frequency_band",
            "registration_status",
            "job_number",
            "pcn_number",
            "rcn_number",
            "call_sign",
            "licensee",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(circuit__cid__icontains=value)
            | Q(pcn_number__icontains=value)
            | Q(rcn_number__icontains=value)
            | Q(licensee__icontains=value)
            | Q(call_sign__icontains=value)
        ).distinct()

    def filter_circuit_cid(self, queryset, name, value):
        return queryset.filter(circuit__cid__icontains=value).distinct()


class WirelessCircuitEndpointFilterSet(NetBoxModelFilterSet):
    wireless_license_profile_id = django_filters.ModelMultipleChoiceFilter(
        field_name="wireless_license_profile",
        queryset=WirelessLicenseProfile.objects.all(),
        label="Wireless license profile (ID)",
    )
    side = django_filters.MultipleChoiceFilter(choices=EndpointSideChoices)
    circuit_cid = django_filters.CharFilter(
        method="filter_circuit_cid",
        label="Circuit CID (contains)",
    )
    netbox_site_id = django_filters.ModelMultipleChoiceFilter(
        field_name="netbox_site",
        queryset=Site.objects.all(),
        label="Site (ID)",
    )
    netbox_device_id = django_filters.ModelMultipleChoiceFilter(
        field_name="netbox_device",
        queryset=Device.objects.all(),
        label="Device (ID)",
    )
    netbox_interface_id = django_filters.ModelMultipleChoiceFilter(
        field_name="netbox_interface",
        queryset=Interface.objects.all(),
        label="Interface (ID)",
    )

    class Meta:
        model = WirelessCircuitEndpoint
        fields = (
            "id",
            "wireless_license_profile",
            "side",
            "netbox_site",
            "netbox_device",
            "netbox_interface",
            "pcn_site_name",
            "polarization",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(wireless_license_profile__circuit__cid__icontains=value)
            | Q(pcn_site_name__icontains=value)
            | Q(antenna_model__icontains=value)
            | Q(radio_model__icontains=value)
        ).distinct()

    def filter_circuit_cid(self, queryset, name, value):
        return queryset.filter(
            wireless_license_profile__circuit__cid__icontains=value
        ).distinct()


class WirelessTargetExceptionFilterSet(NetBoxModelFilterSet):
    wireless_license_profile_id = django_filters.ModelMultipleChoiceFilter(
        field_name="wireless_license_profile",
        queryset=WirelessLicenseProfile.objects.all(),
        label="Wireless license profile (ID)",
    )
    circuit_cid = django_filters.CharFilter(
        method="filter_circuit_cid",
        label="Circuit CID (contains)",
    )
    enabled = django_filters.BooleanFilter()
    suppress_alarms = django_filters.BooleanFilter()

    class Meta:
        model = WirelessTargetException
        fields = (
            "id",
            "wireless_license_profile",
            "enabled",
            "suppress_alarms",
            "approved_by",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(wireless_license_profile__circuit__cid__icontains=value)
            | Q(reason__icontains=value)
        ).distinct()

    def filter_circuit_cid(self, queryset, name, value):
        return queryset.filter(
            wireless_license_profile__circuit__cid__icontains=value
        ).distinct()


class WirelessModulationTargetFilterSet(NetBoxModelFilterSet):
    wireless_license_profile_id = django_filters.ModelMultipleChoiceFilter(
        field_name="wireless_license_profile",
        queryset=WirelessLicenseProfile.objects.all(),
        label="Wireless license profile (ID)",
    )
    circuit = django_filters.ModelMultipleChoiceFilter(
        field_name="wireless_license_profile__circuit",
        queryset=Circuit.objects.all(),
        label="Circuit (ID)",
    )
    circuit_cid = django_filters.CharFilter(
        method="filter_circuit_cid",
        label="Circuit CID (contains)",
    )
    direction = django_filters.MultipleChoiceFilter(choices=ModulationDirectionChoices)
    modulation = django_filters.MultipleChoiceFilter(choices=ModulationChoices)
    alarm_enabled = django_filters.BooleanFilter()

    class Meta:
        model = WirelessModulationTarget
        fields = (
            "id",
            "wireless_license_profile",
            "direction",
            "modulation",
            "modulation_rank",
            "alarm_enabled",
            "radio_model",
            "emission_designator",
        )

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(
            Q(wireless_license_profile__circuit__cid__icontains=value)
            | Q(modulation__icontains=value)
            | Q(radio_model__icontains=value)
        ).distinct()

    def filter_circuit_cid(self, queryset, name, value):
        return queryset.filter(
            wireless_license_profile__circuit__cid__icontains=value
        ).distinct()
