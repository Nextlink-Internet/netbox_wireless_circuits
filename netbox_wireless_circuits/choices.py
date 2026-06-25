from utilities.choices import ChoiceSet


class RegistrationStatusChoices(ChoiceSet):
    """FCC / coordination license workflow status."""

    ENGINEERING = "engineering"
    SUBMITTED = "submitted"
    REGISTERED = "registered"
    GRANTED = "granted"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"

    CHOICES = [
        (ENGINEERING, "Engineering", "cyan"),
        (SUBMITTED, "Submitted", "blue"),
        (REGISTERED, "Registered", "green"),
        (GRANTED, "Granted", "teal"),
        (EXPIRED, "Expired", "red"),
        (CANCELLED, "Cancelled", "gray"),
        (UNKNOWN, "Unknown", "black"),
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
