from netbox.api.routers import NetBoxRouter

from . import views

app_name = "netbox_wireless_circuits"

router = NetBoxRouter()
router.register("wireless-license-profiles", views.WirelessLicenseProfileViewSet)
router.register("wireless-circuit-endpoints", views.WirelessCircuitEndpointViewSet)
router.register("wireless-modulation-targets", views.WirelessModulationTargetViewSet)
router.register("wireless-global-settings", views.WirelessGlobalSettingsViewSet)
router.register("wireless-target-exceptions", views.WirelessTargetExceptionViewSet)

urlpatterns = router.urls
