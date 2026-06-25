from datetime import date

from django.conf import settings
from django.db import models
from django.urls import reverse

from netbox.models import NetBoxModel

from .choices import (
    DEFAULT_RANKS,
    EndpointSideChoices,
    FrequencyBandChoices,
    LLMProviderChoices,
    ModulationChoices,
    ModulationDirectionChoices,
    RegistrationStatusChoices,
)

__all__ = (
    "WirelessLicenseProfile",
    "WirelessCircuitEndpoint",
    "WirelessModulationTarget",
    "WirelessGlobalSettings",
    "WirelessBandTolerance",
    "WirelessTargetException",
    "WirelessLLMSettings",
    "WirelessLLMProvider",
    "WirelessAntenna",
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

    # Carrier aggregation (N+0). carrier_count is the number of bonded RF
    # carriers/channels on the link; radio_configuration is the human notation
    # ("1+0", "2+0", "4+0"), derived from carrier_count at import when not given.
    carrier_count = models.PositiveSmallIntegerField(
        blank=True, null=True,
        verbose_name="Carrier count",
        help_text="Number of bonded RF carriers / channels on the link "
                  "(e.g. 2 for a 2+0 configuration).",
    )
    radio_configuration = models.CharField(
        max_length=20, blank=True,
        verbose_name="Radio configuration",
        help_text="Link aggregation / protection notation, e.g. 1+0, 2+0, 4+0. "
                  "Derived from the carrier count on import when not provided.",
    )

    source_document = models.URLField(blank=True)
    # The actual PCN PDF this profile was imported from, retained on the circuit's
    # wireless record so the source documentation stays attached to the link.
    pcn_document = models.FileField(
        upload_to="netbox-wireless-circuits/pcn/",
        blank=True,
        verbose_name="PCN document",
        help_text="The source PCN PDF, kept for documentation.",
    )
    notes = models.TextField(blank=True)

    # Set by the PCN-PDF import wizard, which CREATES the circuit. When true,
    # deleting this profile also deletes its circuit (and terminations); a
    # profile attached to a pre-existing circuit (manual add) leaves it intact.
    created_via_import = models.BooleanField(
        default=False,
        verbose_name="Created via PCN import",
        help_text="The import wizard created this profile's circuit; deleting "
                  "the profile will also delete that circuit and its terminations.",
    )

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

    def aggregate_data_rate_kbps(self, direction):
        """
        Aggregate expected throughput for a direction: the top alarm-enabled
        modulation's per-carrier data rate × the carrier count. Returns None if
        there is no rate to scale. A blank carrier_count is treated as 1.
        """
        from .zabbix import top_enabled_target

        top = top_enabled_target(self, direction)
        if top is None or top.data_rate_kbps is None:
            return None
        return top.data_rate_kbps * (self.carrier_count or 1)


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
    # Optional link to a reusable antenna in the catalog ("warehouse"). The
    # per-endpoint antenna_* fields below remain (populated from import) for the
    # path-specific record; the catalog holds the shared make/model spec.
    antenna = models.ForeignKey(
        to="WirelessAntenna",
        on_delete=models.SET_NULL,
        related_name="endpoints",
        blank=True,
        null=True,
        help_text="Reusable antenna make/model from the antenna catalog.",
    )
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

    # --- nbxsync (Zabbix) integration ---
    zabbix_sync_enabled = models.BooleanField(
        default=False,
        verbose_name="Zabbix macro sync enabled",
        help_text=(
            "When enabled (and the nbxsync plugin is installed), the plugin "
            "writes per-link expected values to the receiving radio's Zabbix "
            "host as user macros via nbxsync. Off by default."
        ),
    )
    zabbix_macro_prefix = models.CharField(
        max_length=50,
        default="WL",
        verbose_name="Zabbix macro prefix",
        help_text=(
            "Prefix for the generated Zabbix user macros, e.g. 'WL' produces "
            "{$WL.RSL.WARN}. Must match the macro names defined in your Zabbix "
            "wireless template."
        ),
    )
    zabbix_emit_tags = models.BooleanField(
        default=True,
        verbose_name="Emit Zabbix tags",
        help_text=(
            "Also attach nbxsync tags to the radio host classifying it as a "
            "wireless circuit (and its band) for template/trigger targeting."
        ),
    )

    # --- Link-type auto-tagging (NetBox tags) ---
    link_type_tag_enabled = models.BooleanField(
        default=True,
        verbose_name="Auto-tag link type",
        help_text=(
            "Apply a NetBox tag to the circuit reflecting its N+0 radio "
            "configuration (carrier aggregation), e.g. 'link_type: 2+0'."
        ),
    )
    link_type_tag_template = models.CharField(
        max_length=100,
        default="link_type: {config}",
        verbose_name="Link-type tag template",
        help_text=(
            "Template for the link-type tag name; '{config}' is replaced by the "
            "radio configuration (e.g. 2+0). Examples: 'link_type: {config}', "
            "'{config}', 'MW-{config}'."
        ),
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


class WirelessBandTolerance(NetBoxModel):
    """
    Global rule for how many dB off the PCN target is acceptable, **per license
    band**. Overrides the default :attr:`WirelessGlobalSettings.global_tolerance_db`
    for links in that band. A rule of ``0`` means no allowance (must meet target).
    """

    frequency_band = models.CharField(
        max_length=20,
        choices=FrequencyBandChoices,
        unique=True,
        help_text="License band this tolerance rule applies to.",
    )
    tolerance_db = models.DecimalField(
        max_digits=6, decimal_places=2, default=0,
        verbose_name="Tolerance (dB)",
        help_text=(
            "Allowed dB off the PCN target for this band, added to each modulation "
            "target's warning/critical margins. 0 means the link must meet target."
        ),
    )
    enabled = models.BooleanField(
        default=True,
        help_text="If unset, links in this band fall back to the default tolerance.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("frequency_band",)
        verbose_name = "Wireless Band Tolerance"
        verbose_name_plural = "Wireless Band Tolerances"

    def __str__(self):
        return f"{self.frequency_band}: {self.tolerance_db} dB"

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelessbandtolerance", args=[self.pk]
        )


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


class WirelessLLMSettings(NetBoxModel):
    """
    Singleton holding options for the optional PCN-PDF importer. Provider API
    keys are NOT stored here — they come from environment / PLUGINS_CONFIG. This
    only governs whether the importer is on and an optional prompt override; the
    provider fallback chain is modeled by :class:`WirelessLLMProvider` rows.
    """

    pdf_import_enabled = models.BooleanField(
        default=False,
        verbose_name="PCN PDF import enabled",
        help_text=(
            "Enable extracting wireless link fields from an uploaded PCN PDF via "
            "an LLM. Requires at least one configured provider with an API key."
        ),
    )
    prompt_override = models.TextField(
        blank=True,
        help_text=(
            "Optional extra instructions appended to the extraction prompt "
            "(e.g. notes about your PCN document layout)."
        ),
    )
    notes = models.TextField(blank=True)

    class Meta:
        verbose_name = "Wireless LLM Settings"
        verbose_name_plural = "Wireless LLM Settings"

    def __str__(self):
        return "Wireless Circuits LLM Settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):  # pragma: no cover - singleton guard
        pass

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def get_absolute_url(self):
        return reverse("plugins:netbox_wireless_circuits:wirelessllmsettings")


class WirelessLLMProvider(NetBoxModel):
    """
    One entry in the ordered LLM fallback chain for PCN PDF extraction. The
    importer tries enabled providers in ascending ``rank`` order and falls
    through to the next on failure. API keys are resolved from environment /
    PLUGINS_CONFIG by provider, never stored on this row.
    """

    rank = models.PositiveIntegerField(
        default=100,
        help_text="Lower rank is tried first (1 = primary).",
    )
    provider = models.CharField(
        max_length=20,
        choices=LLMProviderChoices,
    )
    model = models.CharField(
        max_length=100,
        help_text="Model identifier, e.g. claude-opus-4-8, gemini-2.5-pro, gpt-4.1.",
    )
    enabled = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("rank", "provider")
        constraints = [
            models.UniqueConstraint(
                fields=["provider", "model"],
                name="wwc_llmprovider_unique_provider_model",
            ),
        ]
        verbose_name = "Wireless LLM Provider"
        verbose_name_plural = "Wireless LLM Providers"

    def __str__(self):
        return f"{self.get_provider_display()} — {self.model} (rank {self.rank})"

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelessllmprovider", args=[self.pk]
        )

    def get_provider_color(self):
        return LLMProviderChoices.colors.get(self.provider)


class WirelessAntenna(NetBoxModel):
    """
    Catalog ("warehouse") of reusable antenna make/models. Endpoints reference an
    entry instead of (or alongside) their free-text antenna fields. The PCN
    importer auto-creates a stub here, keyed by manufacturer + antenna code, when
    it sees an antenna not already in the catalog; the operator then enriches it.
    """

    manufacturer = models.CharField(max_length=200, blank=True)
    antenna_code = models.CharField(
        max_length=100,
        help_text="Vendor antenna code / part number, e.g. 64664A.",
    )
    model = models.CharField(max_length=200, blank=True)
    diameter_ft = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Diameter (ft)",
    )
    diameter_m = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Diameter (m)",
    )
    gain_dbi = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Gain (dBi)",
    )
    beamwidth_deg = models.DecimalField(
        max_digits=7, decimal_places=3, blank=True, null=True,
        verbose_name="Beamwidth (°)",
    )
    polarization = models.CharField(max_length=50, blank=True)
    frequency_range = models.CharField(
        max_length=100, blank=True,
        help_text="Operating frequency range, e.g. '17.7-19.7 GHz'.",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ("manufacturer", "antenna_code")
        constraints = [
            models.UniqueConstraint(
                fields=["manufacturer", "antenna_code"],
                name="wwc_antenna_unique_mfr_code",
            ),
        ]
        verbose_name = "Wireless Antenna"
        verbose_name_plural = "Wireless Antennas"

    def __str__(self):
        label = self.antenna_code or self.model or "antenna"
        return f"{self.manufacturer} {label}".strip()

    def get_absolute_url(self):
        return reverse(
            "plugins:netbox_wireless_circuits:wirelessantenna", args=[self.pk]
        )
