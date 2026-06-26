"""
Base types + shared parsing helpers for CSV import source adapters.

A source adapter subclasses :class:`BaseCSVSource`, declares a machine ``name``
and human ``label``, and implements :meth:`iter_links` to yield :class:`ParsedLink`
objects from an uploaded file. The helpers here (band / modulation / coordinate /
number normalization) are vendor-neutral and reused across adapters.
"""
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from ..choices import FrequencyBandChoices, ModulationChoices

_MOD_VALUES = set(ModulationChoices.values)
_BAND_VALUES = set(FrequencyBandChoices.values)


@dataclass
class ParsedLink:
    """
    One wireless link parsed from a source row, in the plugin's canonical shape.

    ``key`` is the source-stable de-duplication key (re-upload matches on it).
    ``data`` mirrors the PCN extraction structure consumed by
    :func:`netbox_wireless_circuits.pcn_import.create_from_extraction`.
    """
    key: str
    cid: str
    link_id: str = ""
    data: dict = field(default_factory=lambda: {
        "profile": {}, "endpoints": [], "modulation_targets": [],
    })


# --- adapter registry -------------------------------------------------------

_SOURCES = {}


def register_source(cls):
    """Class decorator: register a CSV source adapter by its ``name``."""
    _SOURCES[cls.name] = cls
    return cls


def get_source(name):
    """Return an instance of the registered source, or None."""
    cls = _SOURCES.get(name)
    return cls() if cls else None


def all_sources():
    """All registered source instances, ordered by label."""
    return sorted((cls() for cls in _SOURCES.values()), key=lambda s: s.label)


class BaseCSVSource:
    """Interface every CSV import source implements."""

    name = ""          # machine name, e.g. "comsearch"
    label = ""         # human label shown in the UI
    description = ""    # one-line help shown under the source picker

    def iter_links(self, file_obj):
        """Yield :class:`ParsedLink` for each link in the uploaded file."""
        raise NotImplementedError


# --- vendor-neutral normalization helpers -----------------------------------

def clean_excel(value):
    """Strip Excel's formula-text wrapper, e.g. ``="260623C5"`` -> ``260623C5``."""
    s = (value or "").strip()
    m = re.match(r'^="?(.*?)"?$', s)
    if m:
        s = m.group(1)
    return s.strip().strip('"').strip()


def to_decimal(value):
    """Parse a possibly-messy numeric string to Decimal, or None when blank/NaN."""
    s = (str(value) if value is not None else "").strip().replace(",", "")
    if not s:
        return None
    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def to_int(value):
    d = to_decimal(value)
    return int(d) if d is not None else None


def dms_to_decimal(value):
    """
    Convert a ``D M S H`` coordinate (e.g. ``33 10 52.86 N``) to signed decimal
    degrees. Accepts an already-decimal string too. Returns Decimal or None.
    """
    s = (value or "").strip()
    if not s:
        return None
    m = re.match(
        r"^\s*(\d+(?:\.\d+)?)[\s:]+(\d+(?:\.\d+)?)[\s:]+(\d+(?:\.\d+)?)\s*([NSEWnsew])\s*$",
        s,
    )
    if not m:
        # Maybe it's already a signed decimal value.
        dec = to_decimal(s.rstrip("NSEWnsew ").strip())
        if dec is None:
            return None
        if s.strip()[-1:].upper() in ("S", "W"):
            dec = -dec
        return dec.quantize(Decimal("0.000001"))
    deg, minutes, seconds, hemi = m.groups()
    val = Decimal(deg) + Decimal(minutes) / 60 + Decimal(seconds) / 3600
    if hemi.upper() in ("S", "W"):
        val = -val
    return val.quantize(Decimal("0.000001"))


def normalize_band(value):
    """
    Map a coordinator band label (e.g. ``11 GHz (10700-11700 MHz) US``,
    ``6.1 GHz (5925-6425 MHz) US``) to a :class:`FrequencyBandChoices` value.
    Buckets by the leading GHz figure; returns "" when it can't be placed.
    """
    s = (value or "").strip()
    if not s:
        return ""
    m = re.match(r"\s*(\d+(?:\.\d+)?)", s)
    if not m:
        return ""
    ghz = float(m.group(1))
    if 5.0 <= ghz <= 7.2:
        band = "6 GHz"
    elif 10.0 <= ghz <= 12.0:
        band = "11 GHz"
    elif 17.0 <= ghz <= 20.0:
        band = "18 GHz"
    elif 21.0 <= ghz <= 24.0:
        band = "23 GHz"
    elif 70.0 <= ghz <= 86.0:
        band = "70/80 GHz"
    elif 90.0 <= ghz <= 95.0:
        band = "90 GHz"
    else:
        return ""
    return band if band in _BAND_VALUES else ""


def normalize_modulation(value):
    """
    Map a coordinator modulation token to a :class:`ModulationChoices` value.
    Handles OFDM-prefixed labels (``OFDM 1024QA`` -> ``1024 QAM``) and treats
    4-QAM as QPSK / 2-QAM as BPSK. Returns None when it can't be mapped.
    """
    s = (value or "").strip().upper()
    if not s:
        return None
    if "QPSK" in s:
        return "QPSK"
    if "BPSK" in s:
        return "BPSK"
    m = re.search(r"(\d+)", s)
    if not m:
        return None
    n = int(m.group(1))
    if n == 4:
        return "QPSK"
    if n == 2:
        return "BPSK"
    candidate = f"{n} QAM"
    return candidate if candidate in _MOD_VALUES else None
