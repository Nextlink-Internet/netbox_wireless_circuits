from utilities.choices import ChoiceSet


class RegistrationStatusChoices(ChoiceSet):
    """
    FCC microwave **license status**, using the vocabulary coordinators (e.g.
    Comsearch) report. Tracked per endpoint (each end holds its own license); the
    link-level badge is rolled up from the two ends — see ``rollup_license_status``.
    """

    LICENSED = "licensed"
    APPLIED = "applied"
    PROPOSED = "proposed"
    REPLACED = "replaced"
    EXPIRED_TERMINATED = "expired_terminated"
    TRANSITIONAL = "transitional"
    QUESTIONABLE = "questionable"
    PROTECTION_DECLINED = "protection_declined"
    TEMPORARY = "temporary"
    UNKNOWN = "unknown"

    CHOICES = [
        (LICENSED, "Licensed", "green"),
        (APPLIED, "Applied", "blue"),
        (PROPOSED, "Proposed", "cyan"),
        (REPLACED, "Replaced", "gray"),
        (EXPIRED_TERMINATED, "Expired or Terminated", "red"),
        (TRANSITIONAL, "Transitional", "orange"),
        (QUESTIONABLE, "Questionable", "yellow"),
        (PROTECTION_DECLINED, "Protection Declined", "gray"),
        (TEMPORARY, "Temporary", "purple"),
        (UNKNOWN, "Unknown", "black"),
    ]


# Attention order for the link-level rollup when the two ends differ: earlier =
# surfaced first (the worse / needs-attention status wins the headline badge).
LICENSE_STATUS_PRIORITY = [
    RegistrationStatusChoices.EXPIRED_TERMINATED,
    RegistrationStatusChoices.QUESTIONABLE,
    RegistrationStatusChoices.PROTECTION_DECLINED,
    RegistrationStatusChoices.TRANSITIONAL,
    RegistrationStatusChoices.TEMPORARY,
    RegistrationStatusChoices.REPLACED,
    RegistrationStatusChoices.PROPOSED,
    RegistrationStatusChoices.APPLIED,
    RegistrationStatusChoices.LICENSED,
    RegistrationStatusChoices.UNKNOWN,
]


def rollup_license_status(*statuses):
    """
    Reduce per-end license statuses to a single link-level value: the most
    attention-worthy present status (so a link with one Expired end reads
    'Expired', not 'Licensed'). Returns "" when none are set.
    """
    present = [s for s in statuses if s]
    if not present:
        return ""
    return min(
        present,
        key=lambda s: LICENSE_STATUS_PRIORITY.index(s)
        if s in LICENSE_STATUS_PRIORITY else len(LICENSE_STATUS_PRIORITY),
    )


class LicenseBasisChoices(ChoiceSet):
    """FCC license basis / priority."""

    PRIMARY = "primary"
    SECONDARY = "secondary"

    CHOICES = [
        (PRIMARY, "Primary", "green"),
        (SECONDARY, "Secondary", "yellow"),
    ]


class FrequencyBandChoices(ChoiceSet):
    """Common licensed microwave / millimeter-wave bands."""

    BAND_6 = "6 GHz"
    BAND_11 = "11 GHz"
    BAND_18 = "18 GHz"
    BAND_23 = "23 GHz"
    BAND_7080 = "70/80 GHz"
    BAND_90 = "90 GHz"

    CHOICES = [
        (BAND_6, "6 GHz"),
        (BAND_11, "11 GHz"),
        (BAND_18, "18 GHz"),
        (BAND_23, "23 GHz"),
        (BAND_7080, "70/80 GHz"),
        (BAND_90, "90 GHz"),
    ]


class EndpointSideChoices(ChoiceSet):
    """Endpoint side labels matching native circuit terminations."""

    SIDE_A = "A"
    SIDE_Z = "Z"

    CHOICES = [
        (SIDE_A, "A"),
        (SIDE_Z, "Z"),
    ]


class ModulationDirectionChoices(ChoiceSet):
    """Direction of travel across the wireless path."""

    A_TO_Z = "A_TO_Z"
    Z_TO_A = "Z_TO_A"

    CHOICES = [
        (A_TO_Z, "A → Z"),
        (Z_TO_A, "Z → A"),
    ]


class ModulationChoices(ChoiceSet):
    """Adaptive modulation ladder, from highest order down to BPSK."""

    QAM_4096 = "4096 QAM"
    QAM_2048 = "2048 QAM"
    QAM_1024 = "1024 QAM"
    QAM_512 = "512 QAM"
    QAM_256 = "256 QAM"
    QAM_128 = "128 QAM"
    QAM_64 = "64 QAM"
    QAM_32 = "32 QAM"
    QAM_16 = "16 QAM"
    QPSK = "QPSK"
    BPSK = "BPSK"

    CHOICES = [
        (QAM_4096, "4096 QAM"),
        (QAM_2048, "2048 QAM"),
        (QAM_1024, "1024 QAM"),
        (QAM_512, "512 QAM"),
        (QAM_256, "256 QAM"),
        (QAM_128, "128 QAM"),
        (QAM_64, "64 QAM"),
        (QAM_32, "32 QAM"),
        (QAM_16, "16 QAM"),
        (QPSK, "QPSK"),
        (BPSK, "BPSK"),
    ]


class LLMProviderChoices(ChoiceSet):
    """LLM providers supported for PCN PDF extraction."""

    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    OPENAI = "openai"

    CHOICES = [
        (ANTHROPIC, "Anthropic", "purple"),
        (GEMINI, "Google Gemini", "blue"),
        (OPENAI, "OpenAI", "green"),
    ]


# Canonical rank map. Higher rank == higher-order modulation == more throughput.
# Ranks are intentionally spaced so band-specific ladders can insert values
# between the canonical entries without renumbering.
DEFAULT_RANKS = {
    "4096 QAM": 100,
    "2048 QAM": 90,
    "1024 QAM": 80,
    "512 QAM": 70,
    "256 QAM": 60,
    "128 QAM": 50,
    "64 QAM": 40,
    "32 QAM": 30,
    "16 QAM": 20,
    "QPSK": 10,
    "BPSK": 5,
}
