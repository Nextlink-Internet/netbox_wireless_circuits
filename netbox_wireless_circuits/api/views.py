from rest_framework.decorators import action
from rest_framework.response import Response

from netbox.api.viewsets import NetBoxModelViewSet

from ..choices import EndpointSideChoices, ModulationDirectionChoices
from ..zabbix import (
    effective_critical_rsl,
    effective_tolerance_for_profile,
    effective_warning_rsl,
)
from ..filtersets import (
    WirelessCircuitEndpointFilterSet,
    WirelessLicenseProfileFilterSet,
    WirelessModulationTargetFilterSet,
    WirelessTargetExceptionFilterSet,
)
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
from .serializers import (
    WirelessBandToleranceSerializer,
    WirelessCircuitEndpointSerializer,
    WirelessGlobalSettingsSerializer,
    WirelessLicenseProfileSerializer,
    WirelessLLMProviderSerializer,
    WirelessLLMSettingsSerializer,
    WirelessModulationTargetSerializer,
    WirelessTargetExceptionSerializer,
)


def _decimal_str(value):
    """Render a Decimal as a string, or None when unset."""
    return str(value) if value is not None else None


# Originating endpoint side for each direction of travel.
_ORIGIN_SIDE = {
    ModulationDirectionChoices.A_TO_Z: EndpointSideChoices.SIDE_A,
    ModulationDirectionChoices.Z_TO_A: EndpointSideChoices.SIDE_Z,
}


class WirelessLicenseProfileViewSet(NetBoxModelViewSet):
    queryset = WirelessLicenseProfile.objects.prefetch_related(
        "circuit", "endpoints", "modulation_targets", "tags",
    )
    serializer_class = WirelessLicenseProfileSerializer
    filterset_class = WirelessLicenseProfileFilterSet

    @action(detail=True, methods=["get"], url_path="zabbix")
    def zabbix(self, request, pk=None):
        """
        Return the licensed/expected design intent in a flat shape for Zabbix.

        Without ?direction=, returns a list with both directions. With
        ?direction=A_TO_Z or Z_TO_A, returns a single object for that direction.
        """
        profile = self.get_object()
        direction = request.query_params.get("direction")

        settings_obj = WirelessGlobalSettings.load()
        tolerance = effective_tolerance_for_profile(profile, settings_obj)
        active_exception = next(
            (e for e in profile.exceptions.all() if e.is_active), None
        )
        exception_data = self._exception_dict(active_exception)

        if direction:
            valid = (
                ModulationDirectionChoices.A_TO_Z,
                ModulationDirectionChoices.Z_TO_A,
            )
            if direction not in valid:
                return Response(
                    {"detail": f"Invalid direction '{direction}'. "
                               f"Use A_TO_Z or Z_TO_A."},
                    status=400,
                )
            return Response(
                self._build_direction(profile, direction, tolerance, exception_data)
            )

        return Response([
            self._build_direction(
                profile, ModulationDirectionChoices.A_TO_Z, tolerance, exception_data
            ),
            self._build_direction(
                profile, ModulationDirectionChoices.Z_TO_A, tolerance, exception_data
            ),
        ])

    @staticmethod
    def _exception_dict(exception):
        if exception is None:
            return None
        return {
            "active": True,
            "reason": exception.reason,
            "adjusted_rsl_dbm": _decimal_str(exception.adjusted_rsl_dbm),
            "suppress_alarms": exception.suppress_alarms,
            "effective_date": (
                exception.effective_date.isoformat()
                if exception.effective_date else None
            ),
            "expiry_date": (
                exception.expiry_date.isoformat()
                if exception.expiry_date else None
            ),
            "approved_by": (
                str(exception.approved_by) if exception.approved_by else None
            ),
        }

    def _build_direction(self, profile, direction, tolerance, exception_data):
        origin_side = _ORIGIN_SIDE[direction]
        origin_endpoint = profile.endpoints.filter(side=origin_side).first()

        targets = list(
            profile.modulation_targets.filter(direction=direction).order_by(
                "-modulation_rank"
            )
        )
        top = next((t for t in targets if t.alarm_enabled), None)

        return {
            "circuit_id": profile.circuit_id,
            "cid": profile.circuit.cid,
            "band": profile.frequency_band or None,
            "direction": direction,
            "frequency_mhz": _decimal_str(
                origin_endpoint.tx_frequency_mhz if origin_endpoint else None
            ),
            "top_modulation": top.modulation if top else None,
            "top_modulation_rank": top.modulation_rank if top else None,
            "receiver_threshold_dbm": _decimal_str(profile.receiver_threshold_dbm),
            # Universal allowance (dB) added to each target's margins, plus any
            # active per-link exception. Zabbix uses these to relax/suppress.
            "global_tolerance_db": _decimal_str(tolerance),
            "exception": exception_data,
            "modulation_targets": [
                {
                    "modulation": t.modulation,
                    "modulation_rank": t.modulation_rank,
                    "data_rate_kbps": t.data_rate_kbps,
                    "max_power_dbm": _decimal_str(t.max_power_dbm),
                    "eirp_dbm": _decimal_str(t.eirp_dbm),
                    "expected_rsl_dbm": _decimal_str(t.expected_rsl_dbm),
                    "warning_margin_db": _decimal_str(t.warning_margin_db),
                    "critical_margin_db": _decimal_str(t.critical_margin_db),
                    # expected_rsl - margin - global_tolerance (worse-than = alarm).
                    "effective_warning_rsl_dbm": _decimal_str(
                        effective_warning_rsl(t, tolerance)
                    ),
                    "effective_critical_rsl_dbm": _decimal_str(
                        effective_critical_rsl(t, tolerance)
                    ),
                    "alarm_enabled": t.alarm_enabled,
                }
                for t in targets
            ],
        }


class WirelessCircuitEndpointViewSet(NetBoxModelViewSet):
    queryset = WirelessCircuitEndpoint.objects.prefetch_related(
        "wireless_license_profile", "netbox_site", "netbox_device",
        "netbox_interface", "tags",
    )
    serializer_class = WirelessCircuitEndpointSerializer
    filterset_class = WirelessCircuitEndpointFilterSet


class WirelessModulationTargetViewSet(NetBoxModelViewSet):
    queryset = WirelessModulationTarget.objects.prefetch_related(
        "wireless_license_profile", "tags",
    )
    serializer_class = WirelessModulationTargetSerializer
    filterset_class = WirelessModulationTargetFilterSet


class WirelessGlobalSettingsViewSet(NetBoxModelViewSet):
    queryset = WirelessGlobalSettings.objects.prefetch_related("tags")
    serializer_class = WirelessGlobalSettingsSerializer


class WirelessTargetExceptionViewSet(NetBoxModelViewSet):
    queryset = WirelessTargetException.objects.prefetch_related(
        "wireless_license_profile", "approved_by", "tags",
    )
    serializer_class = WirelessTargetExceptionSerializer
    filterset_class = WirelessTargetExceptionFilterSet


class WirelessBandToleranceViewSet(NetBoxModelViewSet):
    queryset = WirelessBandTolerance.objects.prefetch_related("tags")
    serializer_class = WirelessBandToleranceSerializer


class WirelessLLMSettingsViewSet(NetBoxModelViewSet):
    queryset = WirelessLLMSettings.objects.prefetch_related("tags")
    serializer_class = WirelessLLMSettingsSerializer


class WirelessLLMProviderViewSet(NetBoxModelViewSet):
    queryset = WirelessLLMProvider.objects.prefetch_related("tags")
    serializer_class = WirelessLLMProviderSerializer
