from django.urls import path

from netbox.views.generic import ObjectChangeLogView, ObjectJournalView

from . import models, views

app_name = "netbox_wireless_circuits"

urlpatterns = [
    # --- Wireless License Profiles ---
    path(
        "wireless-license-profiles/",
        views.WirelessLicenseProfileListView.as_view(),
        name="wirelesslicenseprofile_list",
    ),
    path(
        "wireless-license-profiles/add/",
        views.WirelessLicenseProfileEditView.as_view(),
        name="wirelesslicenseprofile_add",
    ),
    path(
        "wireless-license-profiles/import/",
        views.WirelessLicenseProfileBulkImportView.as_view(),
        name="wirelesslicenseprofile_import",
    ),
    path(
        "wireless-license-profiles/delete/",
        views.WirelessLicenseProfileBulkDeleteView.as_view(),
        name="wirelesslicenseprofile_bulk_delete",
    ),
    path(
        "wireless-license-profiles/<int:pk>/",
        views.WirelessLicenseProfileView.as_view(),
        name="wirelesslicenseprofile",
    ),
    path(
        "wireless-license-profiles/<int:pk>/edit/",
        views.WirelessLicenseProfileEditView.as_view(),
        name="wirelesslicenseprofile_edit",
    ),
    path(
        "wireless-license-profiles/<int:pk>/delete/",
        views.WirelessLicenseProfileDeleteView.as_view(),
        name="wirelesslicenseprofile_delete",
    ),
    path(
        "wireless-license-profiles/<int:pk>/sync-zabbix/",
        views.WirelessLicenseProfileZabbixSyncView.as_view(),
        name="wirelesslicenseprofile_sync_zabbix",
    ),
    path(
        "wireless-license-profiles/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="wirelesslicenseprofile_changelog",
        kwargs={"model": models.WirelessLicenseProfile},
    ),
    path(
        "wireless-license-profiles/<int:pk>/journal/",
        ObjectJournalView.as_view(),
        name="wirelesslicenseprofile_journal",
        kwargs={"model": models.WirelessLicenseProfile},
    ),

    # --- Wireless Circuit Endpoints ---
    path(
        "wireless-circuit-endpoints/",
        views.WirelessCircuitEndpointListView.as_view(),
        name="wirelesscircuitendpoint_list",
    ),
    path(
        "wireless-circuit-endpoints/add/",
        views.WirelessCircuitEndpointEditView.as_view(),
        name="wirelesscircuitendpoint_add",
    ),
    path(
        "wireless-circuit-endpoints/delete/",
        views.WirelessCircuitEndpointBulkDeleteView.as_view(),
        name="wirelesscircuitendpoint_bulk_delete",
    ),
    path(
        "wireless-circuit-endpoints/<int:pk>/",
        views.WirelessCircuitEndpointView.as_view(),
        name="wirelesscircuitendpoint",
    ),
    path(
        "wireless-circuit-endpoints/<int:pk>/edit/",
        views.WirelessCircuitEndpointEditView.as_view(),
        name="wirelesscircuitendpoint_edit",
    ),
    path(
        "wireless-circuit-endpoints/<int:pk>/delete/",
        views.WirelessCircuitEndpointDeleteView.as_view(),
        name="wirelesscircuitendpoint_delete",
    ),
    path(
        "wireless-circuit-endpoints/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="wirelesscircuitendpoint_changelog",
        kwargs={"model": models.WirelessCircuitEndpoint},
    ),
    path(
        "wireless-circuit-endpoints/<int:pk>/journal/",
        ObjectJournalView.as_view(),
        name="wirelesscircuitendpoint_journal",
        kwargs={"model": models.WirelessCircuitEndpoint},
    ),

    # --- Wireless Modulation Targets ---
    path(
        "wireless-modulation-targets/",
        views.WirelessModulationTargetListView.as_view(),
        name="wirelessmodulationtarget_list",
    ),
    path(
        "wireless-modulation-targets/add/",
        views.WirelessModulationTargetEditView.as_view(),
        name="wirelessmodulationtarget_add",
    ),
    path(
        "wireless-modulation-targets/import/",
        views.WirelessModulationTargetBulkImportView.as_view(),
        name="wirelessmodulationtarget_import",
    ),
    path(
        "wireless-modulation-targets/delete/",
        views.WirelessModulationTargetBulkDeleteView.as_view(),
        name="wirelessmodulationtarget_bulk_delete",
    ),
    path(
        "wireless-modulation-targets/<int:pk>/",
        views.WirelessModulationTargetView.as_view(),
        name="wirelessmodulationtarget",
    ),
    path(
        "wireless-modulation-targets/<int:pk>/edit/",
        views.WirelessModulationTargetEditView.as_view(),
        name="wirelessmodulationtarget_edit",
    ),
    path(
        "wireless-modulation-targets/<int:pk>/delete/",
        views.WirelessModulationTargetDeleteView.as_view(),
        name="wirelessmodulationtarget_delete",
    ),
    path(
        "wireless-modulation-targets/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="wirelessmodulationtarget_changelog",
        kwargs={"model": models.WirelessModulationTarget},
    ),
    path(
        "wireless-modulation-targets/<int:pk>/journal/",
        ObjectJournalView.as_view(),
        name="wirelessmodulationtarget_journal",
        kwargs={"model": models.WirelessModulationTarget},
    ),

    # --- Global Settings (singleton; the page is the edit form) ---
    path(
        "global-settings/",
        views.WirelessGlobalSettingsEditView.as_view(),
        name="wirelessglobalsettings",
    ),
    path(
        "global-settings/edit/",
        views.WirelessGlobalSettingsEditView.as_view(),
        name="wirelessglobalsettings_edit",
    ),

    # --- Target Exceptions ---
    path(
        "target-exceptions/",
        views.WirelessTargetExceptionListView.as_view(),
        name="wirelesstargetexception_list",
    ),
    path(
        "target-exceptions/add/",
        views.WirelessTargetExceptionEditView.as_view(),
        name="wirelesstargetexception_add",
    ),
    path(
        "target-exceptions/delete/",
        views.WirelessTargetExceptionBulkDeleteView.as_view(),
        name="wirelesstargetexception_bulk_delete",
    ),
    path(
        "target-exceptions/<int:pk>/",
        views.WirelessTargetExceptionView.as_view(),
        name="wirelesstargetexception",
    ),
    path(
        "target-exceptions/<int:pk>/edit/",
        views.WirelessTargetExceptionEditView.as_view(),
        name="wirelesstargetexception_edit",
    ),
    path(
        "target-exceptions/<int:pk>/delete/",
        views.WirelessTargetExceptionDeleteView.as_view(),
        name="wirelesstargetexception_delete",
    ),
    path(
        "target-exceptions/<int:pk>/changelog/",
        ObjectChangeLogView.as_view(),
        name="wirelesstargetexception_changelog",
        kwargs={"model": models.WirelessTargetException},
    ),
    path(
        "target-exceptions/<int:pk>/journal/",
        ObjectJournalView.as_view(),
        name="wirelesstargetexception_journal",
        kwargs={"model": models.WirelessTargetException},
    ),
]
