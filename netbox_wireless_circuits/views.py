from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import View

from circuits.models import Circuit
from netbox.views import generic
from utilities.views import ViewTab, register_model_view

from . import filtersets, forms, models, tables
from .nbxsync_sync import nbxsync_available, sync_enabled, sync_profile


# ---------------------------------------------------------------------------
# WirelessLicenseProfile
# ---------------------------------------------------------------------------

class WirelessLicenseProfileView(generic.ObjectView):
    queryset = models.WirelessLicenseProfile.objects.all()

    def get_extra_context(self, request, instance):
        return {
            "endpoint_a": instance.endpoints.filter(side="A").first(),
            "endpoint_z": instance.endpoints.filter(side="Z").first(),
            "mod_a_to_z": instance.modulation_targets.filter(
                direction="A_TO_Z"
            ).order_by("-modulation_rank"),
            "mod_z_to_a": instance.modulation_targets.filter(
                direction="Z_TO_A"
            ).order_by("-modulation_rank"),
            "exceptions": instance.exceptions.all(),
            "global_settings": models.WirelessGlobalSettings.load(),
            "zabbix_sync_available": sync_enabled(),
        }


class WirelessLicenseProfileZabbixSyncView(View):
    """POST action: push this link's expected values to nbxsync Zabbix macros."""

    def post(self, request, pk):
        profile = get_object_or_404(models.WirelessLicenseProfile, pk=pk)
        if not request.user.has_perm(
            "netbox_wireless_circuits.change_wirelesslicenseprofile"
        ):
            raise PermissionDenied()

        if not nbxsync_available():
            messages.error(request, "nbxsync is not installed; cannot sync to Zabbix.")
        elif not sync_enabled():
            messages.warning(
                request,
                "Zabbix macro sync is disabled in Wireless Global Settings.",
            )
        else:
            results = sync_profile(profile)
            macros = sum(r["macros_written"] for r in results)
            missing = sorted({m for r in results for m in r["macros_missing_def"]})
            messages.success(
                request,
                f"Synced {len(results)} device(s): {macros} macro assignment(s).",
            )
            if missing:
                messages.warning(
                    request,
                    "Missing macro definitions (define them in your Zabbix "
                    "wireless template): " + ", ".join(missing),
                )
        return redirect(profile.get_absolute_url())


class WirelessLicenseProfileListView(generic.ObjectListView):
    queryset = models.WirelessLicenseProfile.objects.all()
    table = tables.WirelessLicenseProfileTable
    filterset = filtersets.WirelessLicenseProfileFilterSet


class WirelessLicenseProfileEditView(generic.ObjectEditView):
    queryset = models.WirelessLicenseProfile.objects.all()
    form = forms.WirelessLicenseProfileForm


class WirelessLicenseProfileDeleteView(generic.ObjectDeleteView):
    queryset = models.WirelessLicenseProfile.objects.all()


class WirelessLicenseProfileBulkImportView(generic.BulkImportView):
    queryset = models.WirelessLicenseProfile.objects.all()
    model_form = forms.WirelessLicenseProfileImportForm


class WirelessLicenseProfileBulkDeleteView(generic.BulkDeleteView):
    queryset = models.WirelessLicenseProfile.objects.all()
    table = tables.WirelessLicenseProfileTable


# ---------------------------------------------------------------------------
# WirelessCircuitEndpoint
# ---------------------------------------------------------------------------

class WirelessCircuitEndpointView(generic.ObjectView):
    queryset = models.WirelessCircuitEndpoint.objects.all()


class WirelessCircuitEndpointListView(generic.ObjectListView):
    queryset = models.WirelessCircuitEndpoint.objects.all()
    table = tables.WirelessCircuitEndpointTable
    filterset = filtersets.WirelessCircuitEndpointFilterSet


class WirelessCircuitEndpointEditView(generic.ObjectEditView):
    queryset = models.WirelessCircuitEndpoint.objects.all()
    form = forms.WirelessCircuitEndpointForm


class WirelessCircuitEndpointDeleteView(generic.ObjectDeleteView):
    queryset = models.WirelessCircuitEndpoint.objects.all()


class WirelessCircuitEndpointBulkDeleteView(generic.BulkDeleteView):
    queryset = models.WirelessCircuitEndpoint.objects.all()
    table = tables.WirelessCircuitEndpointTable


# ---------------------------------------------------------------------------
# WirelessModulationTarget
# ---------------------------------------------------------------------------

class WirelessModulationTargetView(generic.ObjectView):
    queryset = models.WirelessModulationTarget.objects.all()


class WirelessModulationTargetListView(generic.ObjectListView):
    queryset = models.WirelessModulationTarget.objects.all()
    table = tables.WirelessModulationTargetTable
    filterset = filtersets.WirelessModulationTargetFilterSet


class WirelessModulationTargetEditView(generic.ObjectEditView):
    queryset = models.WirelessModulationTarget.objects.all()
    form = forms.WirelessModulationTargetForm


class WirelessModulationTargetDeleteView(generic.ObjectDeleteView):
    queryset = models.WirelessModulationTarget.objects.all()


class WirelessModulationTargetBulkImportView(generic.BulkImportView):
    queryset = models.WirelessModulationTarget.objects.all()
    model_form = forms.WirelessModulationTargetImportForm


class WirelessModulationTargetBulkDeleteView(generic.BulkDeleteView):
    queryset = models.WirelessModulationTarget.objects.all()
    table = tables.WirelessModulationTargetTable


# ---------------------------------------------------------------------------
# WirelessGlobalSettings (singleton)
# ---------------------------------------------------------------------------

class WirelessGlobalSettingsEditView(generic.ObjectEditView):
    """The Global Settings 'page' is the edit form itself (singleton)."""
    queryset = models.WirelessGlobalSettings.objects.all()
    form = forms.WirelessGlobalSettingsForm

    def get_object(self, **kwargs):
        return models.WirelessGlobalSettings.load()


# ---------------------------------------------------------------------------
# WirelessLLMSettings (singleton) + WirelessLLMProvider chain
# ---------------------------------------------------------------------------

class WirelessLLMSettingsEditView(generic.ObjectEditView):
    """The LLM Settings 'page' is the edit form itself (singleton)."""
    queryset = models.WirelessLLMSettings.objects.all()
    form = forms.WirelessLLMSettingsForm

    def get_object(self, **kwargs):
        return models.WirelessLLMSettings.load()


class WirelessLLMProviderView(generic.ObjectView):
    queryset = models.WirelessLLMProvider.objects.all()

    def get_extra_context(self, request, instance):
        from .llm import provider_status

        return {"status": provider_status(instance.provider)}


class WirelessLLMProviderListView(generic.ObjectListView):
    queryset = models.WirelessLLMProvider.objects.all()
    table = tables.WirelessLLMProviderTable


class WirelessLLMProviderEditView(generic.ObjectEditView):
    queryset = models.WirelessLLMProvider.objects.all()
    form = forms.WirelessLLMProviderForm


class WirelessLLMProviderDeleteView(generic.ObjectDeleteView):
    queryset = models.WirelessLLMProvider.objects.all()


class WirelessLLMProviderBulkDeleteView(generic.BulkDeleteView):
    queryset = models.WirelessLLMProvider.objects.all()
    table = tables.WirelessLLMProviderTable


# ---------------------------------------------------------------------------
# WirelessTargetException
# ---------------------------------------------------------------------------

class WirelessTargetExceptionView(generic.ObjectView):
    queryset = models.WirelessTargetException.objects.all()


class WirelessTargetExceptionListView(generic.ObjectListView):
    queryset = models.WirelessTargetException.objects.all()
    table = tables.WirelessTargetExceptionTable
    filterset = filtersets.WirelessTargetExceptionFilterSet


class WirelessTargetExceptionEditView(generic.ObjectEditView):
    queryset = models.WirelessTargetException.objects.all()
    form = forms.WirelessTargetExceptionForm

    def alter_object(self, obj, request, url_args, url_kwargs):
        # Record who approved the exception on creation; never overwrite on edit.
        if not obj.pk and getattr(obj, "approved_by_id", None) is None:
            obj.approved_by = request.user
        return obj


class WirelessTargetExceptionDeleteView(generic.ObjectDeleteView):
    queryset = models.WirelessTargetException.objects.all()


class WirelessTargetExceptionBulkDeleteView(generic.BulkDeleteView):
    queryset = models.WirelessTargetException.objects.all()
    table = tables.WirelessTargetExceptionTable


# ---------------------------------------------------------------------------
# Circuit detail-page tab: "Wireless License"
# ---------------------------------------------------------------------------

def _wireless_tab_badge(obj):
    return 1 if WirelessLicenseProfile_exists(obj) else 0


def WirelessLicenseProfile_exists(circuit):
    try:
        return circuit.wireless_license_profile is not None
    except models.WirelessLicenseProfile.DoesNotExist:
        return False


@register_model_view(Circuit, name="wireless", path="wireless")
class CircuitWirelessLicenseView(generic.ObjectView):
    queryset = Circuit.objects.all()
    template_name = "netbox_wireless_circuits/circuit_wireless_tab.html"
    tab = ViewTab(
        label="Wireless License",
        badge=_wireless_tab_badge,
        hide_if_empty=False,
    )

    def get_extra_context(self, request, instance):
        try:
            profile = instance.wireless_license_profile
        except models.WirelessLicenseProfile.DoesNotExist:
            profile = None

        context = {"profile": profile}
        if profile is not None:
            context.update({
                "endpoint_a": profile.endpoints.filter(side="A").first(),
                "endpoint_z": profile.endpoints.filter(side="Z").first(),
                "mod_a_to_z": profile.modulation_targets.filter(
                    direction="A_TO_Z"
                ).order_by("-modulation_rank"),
                "mod_z_to_a": profile.modulation_targets.filter(
                    direction="Z_TO_A"
                ).order_by("-modulation_rank"),
                "exceptions": profile.exceptions.all(),
                "global_settings": models.WirelessGlobalSettings.load(),
            })
        return context
