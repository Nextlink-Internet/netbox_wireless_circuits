from datetime import date

from django.conf import settings
from django.db import models
from django.urls import reverse

from netbox.models import NetBoxModel

from .choices import (
    DEFAULT_RANKS,
    EndpointSideChoices,
    FrequencyBandChoices,
    ModulationChoices,
    ModulationDirectionChoices,
    RegistrationStatusChoices,
)

__all__ = (
    "WirelessLicenseProfile",
    "WirelessCircuitEndpoint",
    "WirelessModulationTarget",
    "WirelessGlobalSettings",
    "WirelessTargetException",
)


class WirelessLicenseProfile(NetBoxModel):
    """
    One license / design profile per native NetBox Circuit. Stores the licensed
    / coordinated intent (PCN, FCC registration, path engineering) that Zabbix
    compares live telemetry against.
    """

    circuit = models.OneToOneField(
        to="circuits.Circuit",
        on_delete=models.CASCADE,
        related_name="wireless_license_profile",
        help_text="Native NetBox circuit this wireless license profile describes.",
    )

    # License / PCN workflow
    pcn_date = models.DateField(blank=True, null=True)
    job_number = models.CharField(max_length=100, blank=True)
    pcn_number = models.CharField(max_length=100, blank=True)
    rcn_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="RCN / Link Registration Number",
    )
    registration_status = models.CharField(
        max_length=30,
        choices=RegistrationStatusChoices,
        default=RegistrationStatusChoices.UNKNOWN,
        blank=True,
    )
    registration_date = models.DateField(blank=True, null=True)
    registration_completion_date = models.DateField(blank=True, null=True)

    # Licensee / station identity
    licensee = models.CharField(max_length=200, blank=True)
    call_sign = models.CharField(max_length=50, blank=True)
    radio_service = models.CharField(max_length=100, blank=True)
    station_class = models.CharField(max_length=100, blank=True)

    # RF / path engineering
    frequency_band = models.CharField(
        max_length=20,
        choices=FrequencyBandChoices,
        blank=True,
    )
    channel_plan_mhz = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Channel plan (MHz)",
    )
    path_length_km = models.DecimalField(
        max_digits=10, decimal_places=4, blank=True, null=True,
        verbose_name="Path length (km)",
    )
    path_length_miles = models.DecimalField(
        max_digits=10, decimal_places=4, blank=True, null=True,
        verbose_name="Path length (miles)",
    )
    atmospheric_loss_db = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Atmospheric loss (dB)",
    )
    free_space_loss_db = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Free space loss (dB)",
    )
    receiver_threshold_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Receiver threshold (dBm)",
    )

    source_document = models.URLField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("circuit",)
        verbose_name = "Wireless License Profile"
        verbose_name_plural = "Wireless License Profiles"

    def __str__(self):
        try:
            return f"Wireless License: {self.circuit.cid}"
        except Exception:
            return f"Wireless License Profile {self.pk}"

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelesslicenseprofile",
            args=[self.pk],
        )

    def get_registration_status_color(self):
        return RegistrationStatusChoices.colors.get(self.registration_status)

    def endpoint_for_side(self, side):
        """Return the endpoint for a given side ('A'/'Z') or None."""
        return self.endpoints.filter(side=side).first()


class WirelessCircuitEndpoint(NetBoxModel):
    """RF and site engineering data for one end (A or Z) of the wireless path."""

    wireless_license_profile = models.ForeignKey(
        to=WirelessLicenseProfile,
        on_delete=models.CASCADE,
        related_name="endpoints",
    )
    side = models.CharField(
        max_length=1,
        choices=EndpointSideChoices,
    )

    # NetBox object linkage (all optional; not required at creation)
    netbox_site = models.ForeignKey(
        to="dcim.Site",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    netbox_device = models.ForeignKey(
        to="dcim.Device",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )
    netbox_interface = models.ForeignKey(
        to="dcim.Interface",
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
    )

    # Site identity
    pcn_site_name = models.CharField(max_length=200, blank=True)
    county_state = models.CharField(max_length=200, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True,
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, blank=True, null=True,
    )
    ground_elevation_m = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Ground elevation (m)",
    )
    ground_elevation_ft = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Ground elevation (ft)",
    )
    asr_number = models.CharField(max_length=50, blank=True, verbose_name="ASR number")
    structure_height_agl_m = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Structure height AGL (m)",
    )
    structure_height_agl_ft = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Structure height AGL (ft)",
    )

    # Antenna
    path_azimuth_deg = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Path azimuth (°)",
    )
    antenna_code = models.CharField(max_length=100, blank=True)
    antenna_manufacturer = models.CharField(max_length=200, blank=True)
    antenna_model = models.CharField(max_length=200, blank=True)
    antenna_diameter_ft = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Antenna diameter (ft)",
    )
    antenna_gain_dbi = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Antenna gain (dBi)",
    )
    antenna_beamwidth_deg = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Antenna beamwidth (°)",
    )
    antenna_tilt_deg = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Antenna tilt (°)",
    )
    centerline_agl_m = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Centerline AGL (m)",
    )
    centerline_agl_ft = models.DecimalField(
        max_digits=10, decimal_places=3, blank=True, null=True,
        verbose_name="Centerline AGL (ft)",
    )

    # Radio
    transmit_mode = models.CharField(max_length=100, blank=True)
    radio_code = models.CharField(max_length=100, blank=True)
    radio_manufacturer = models.CharField(max_length=200, blank=True)
    radio_model = models.CharField(max_length=200, blank=True)
    radio_description = models.CharField(max_length=255, blank=True)
    stability_percent = models.DecimalField(
        max_digits=10, decimal_places=6, blank=True, null=True,
        verbose_name="Stability (%)",
    )

    # Power / RSL design points (dBm)
    nominal_power_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Nominal power (dBm)",
    )
    nominal_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Nominal RSL (dBm)",
    )
    coordinated_power_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Coordinated power (dBm)",
    )
    coordinated_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Coordinated RSL (dBm)",
    )
    maximum_power_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Maximum power (dBm)",
    )
    maximum_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Maximum RSL (dBm)",
    )

    # Fixed losses (dB)
    fixed_loss_common_db = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Fixed loss common (dB)",
    )
    fixed_loss_tx_db = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Fixed loss TX (dB)",
    )
    fixed_loss_rx_db = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Fixed loss RX (dB)",
    )

    tx_frequency_mhz = models.DecimalField(
        max_digits=12, decimal_places=3, blank=True, null=True,
        verbose_name="TX frequency (MHz)",
    )
    polarization = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ("wireless_license_profile", "side")
        constraints = [
            models.UniqueConstraint(
                fields=["wireless_license_profile", "side"],
                name="wwc_endpoint_unique_profile_side",
            ),
        ]
        verbose_name = "Wireless Circuit Endpoint"
        verbose_name_plural = "Wireless Circuit Endpoints"

    def __str__(self):
        try:
            return f"{self.wireless_license_profile.circuit.cid} — Side {self.side}"
        except Exception:
            return f"Endpoint {self.pk} (Side {self.side})"

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelesscircuitendpoint",
            args=[self.pk],
        )

    def get_side_color(self):
        return {"A": "blue", "Z": "purple"}.get(self.side, "gray")


class WirelessModulationTarget(NetBoxModel):
    """
    Expected modulation ladder entry and alarm thresholds for one direction of
    travel. Not assumed uniform across frequency bands.
    """

    wireless_license_profile = models.ForeignKey(
        to=WirelessLicenseProfile,
        on_delete=models.CASCADE,
        related_name="modulation_targets",
    )
    direction = models.CharField(
        max_length=10,
        choices=ModulationDirectionChoices,
    )
    modulation = models.CharField(
        max_length=20,
        choices=ModulationChoices,
    )
    modulation_rank = models.PositiveIntegerField(blank=True, null=True)

    radio_model = models.CharField(max_length=200, blank=True)
    emission_designator = models.CharField(max_length=100, blank=True)
    data_rate_kbps = models.PositiveIntegerField(blank=True, null=True)

    max_power_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Max power (dBm)",
    )
    eirp_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="EIRP (dBm)",
    )
    expected_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Expected RSL (dBm)",
    )
    min_acceptable_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Min acceptable RSL (dBm)",
    )
    max_acceptable_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Max acceptable RSL (dBm)",
    )
    warning_margin_db = models.DecimalField(
        max_digits=6, decimal_places=2, default=3.0,
        verbose_name="Warning margin (dB)",
    )
    critical_margin_db = models.DecimalField(
        max_digits=6, decimal_places=2, default=6.0,
        verbose_name="Critical margin (dB)",
    )
    alarm_enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("wireless_license_profile", "direction", "-modulation_rank")
        constraints = [
            models.UniqueConstraint(
                fields=["wireless_license_profile", "direction", "modulation"],
                name="wwc_modtarget_unique_profile_direction_modulation",
            ),
        ]
        verbose_name = "Wireless Modulation Target"
        verbose_name_plural = "Wireless Modulation Targets"

    def __str__(self):
        return f"{self.get_direction_display()} — {self.modulation}"

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelessmodulationtarget",
            args=[self.pk],
        )

    def save(self, *args, **kwargs):
        # Auto-fill the rank from the canonical map when it is null, zero, or blank.
        if not self.modulation_rank:
            self.modulation_rank = DEFAULT_RANKS.get(self.modulation, 0)
        super().save(*args, **kwargs)


class WirelessGlobalSettings(NetBoxModel):
    """
    Singleton holding plugin-wide settings. The most important is a universal
    tolerance (dB) that loosens every link's acceptable RSL thresholds. Editable
    in the UI by users granted the change permission; changes are change-logged.
    """

    global_tolerance_db = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Global tolerance (dB)",
        help_text=(
            "Universal allowance added on top of each modulation target's "
            "warning/critical margins. e.g. target -38 dBm with a 2 dB tolerance "
            "treats -40 dBm as still acceptable."
        ),
    )
    tolerance_enabled = models.BooleanField(
        default=True,
        help_text="If unset, the global tolerance is ignored (treated as 0).",
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Wireless Global Settings"
        verbose_name_plural = "Wireless Global Settings"

    def __str__(self):
        return "Wireless Circuits Global Settings"

    def save(self, *args, **kwargs):
        # Enforce a single row.
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - singleton guard
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @property
    def effective_tolerance_db(self):
        from decimal import Decimal
        if not self.tolerance_enabled:
            return Decimal("0")
        return self.global_tolerance_db or Decimal("0")

    def get_absolute_url(self):
        # The settings "page" is the edit form itself (singleton).
        return reverse("plugins:netbox_wireless_circuits:wirelessglobalsettings")


class WirelessTargetException(NetBoxModel):
    """
    Records that a link is permitted not to meet its PCN target (for any reason).
    Applies to the whole link. Creation/modification is intended to be restricted
    to an approver group via NetBox object permissions; ``approved_by`` and the
    change log provide the audit trail.
    """

    wireless_license_profile = models.ForeignKey(
        to=WirelessLicenseProfile,
        on_delete=models.CASCADE,
        related_name="exceptions",
    )
    reason = models.TextField(
        help_text="Why this link cannot meet its PCN target.",
    )
    approved_by = models.ForeignKey(
        to=settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="+",
        blank=True,
        null=True,
        help_text="Set automatically to the user who creates the exception.",
    )
    effective_date = models.DateField(blank=True, null=True)
    expiry_date = models.DateField(
        blank=True, null=True,
        help_text="After this date the exception lapses automatically.",
    )
    adjusted_rsl_dbm = models.DecimalField(
        max_digits=8, decimal_places=3, blank=True, null=True,
        verbose_name="Adjusted RSL (dBm)",
        help_text=(
            "Agreed achievable RSL to alarm against instead of the PCN target. "
            "Leave blank and enable 'suppress alarms' to silence RSL alarms entirely."
        ),
    )
    suppress_alarms = models.BooleanField(
        default=False,
        help_text="Suppress target-miss alarms for this link entirely.",
    )
    enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("wireless_license_profile", "-effective_date")
        verbose_name = "Wireless Target Exception"
        verbose_name_plural = "Wireless Target Exceptions"

    def __str__(self):
        try:
            return f"Exception: {self.wireless_license_profile.circuit.cid}"
        except Exception:
            return f"Wireless Target Exception {self.pk}"

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelesstargetexception",
            args=[self.pk],
        )

    @property
    def is_active(self):
        if not self.enabled:
            return False
        today = date.today()
        if self.effective_date and today < self.effective_date:
            return False
        if self.expiry_date and today > self.expiry_date:
            return False
        return True
