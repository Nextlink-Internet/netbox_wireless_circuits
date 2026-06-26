from netbox.api.routers import NetBoxRouter

from . import views

app_name = "netbox_wireless_circuits"

router = NetBoxRouter()
router.register("wireless-license-profiles", views.WirelessLicenseProfileViewSet)
router.register("wireless-circuit-endpoints", views.WirelessCircuitEndpointViewSet)
router.register("wireless-modulation-targets", views.WirelessModulationTargetViewSet)
router.register("wireless-global-settings", views.WirelessGlobalSettingsViewSet)
router.register("wireless-band-tolerances", views.WirelessBandToleranceViewSet)
router.register("wireless-import-status-maps", views.WirelessImportStatusMapViewSet)
router.register("wireless-antennas", views.WirelessAntennaViewSet)
router.register("wireless-target-exceptions", views.WirelessTargetExceptionViewSet)
router.register("wireless-llm-settings", views.WirelessLLMSettingsViewSet)
router.register("wireless-llm-providers", views.WirelessLLMProviderViewSet)

urlpatterns = router.urls
