"""
Optional LLM-assisted extraction of wireless link fields from a PCN PDF.

Design:
- **API keys never live in the database.** They are resolved from
  ``PLUGINS_CONFIG['netbox_wireless_circuits']['llm_api_keys'][<provider>]`` or,
  failing that, an environment variable (``ANTHROPIC_API_KEY`` /
  ``GEMINI_API_KEY`` / ``OPENAI_API_KEY``).
- The **fallback chain** is the ordered set of enabled
  :class:`~netbox_wireless_circuits.models.WirelessLLMProvider` rows; the importer
  walks them by ascending ``rank`` and falls through to the next on any failure
  (SDK missing, no key, API error, unparseable output).
- Provider SDKs are **optional extras** (``pip install
  netbox-wireless-circuits[llm]``); a provider whose SDK isn't installed is simply
  skipped in the chain.

The configuration + failover logic here is pure and unit-tested via dependency
injection; the per-vendor adapters are thin and validated live.
"""
import importlib.util
import json
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger("netbox_wireless_circuits")

PLUGIN = "netbox_wireless_circuits"

ENV_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openai": "OPENAI_API_KEY",
}
SDK_IMPORT = {
    "anthropic": "anthropic",
    "gemini": "google.genai",
    "openai": "openai",
}


class ProviderError(Exception):
    """Raised when every provider in the chain fails."""


@dataclass
class ExtractionResult:
    provider: str
    model: str
    data: dict
    attempts: list = field(default_factory=list)


# --- key + SDK resolution (no DB) ---

def get_api_key(provider):
    """Resolve a provider's API key from PLUGINS_CONFIG, then environment."""
    configured = {}
    try:
        from netbox.plugins import get_plugin_config

        configured = get_plugin_config(PLUGIN, "llm_api_keys", default={}) or {}
    except Exception:  # pragma: no cover - defensive
        configured = {}
    if configured.get(provider):
        return configured[provider]
    env = ENV_KEYS.get(provider)
    return os.environ.get(env) if env else None


def key_present(provider):
    return bool(get_api_key(provider))


def sdk_available(provider):
    module = SDK_IMPORT.get(provider)
    if not module:
        return False
    try:
        return importlib.util.find_spec(module) is not None
    except (ImportError, ValueError):  # pragma: no cover - defensive
        return False


def provider_status(provider):
    """UI helper: (sdk_available, key_present) without revealing the key."""
    return {"sdk": sdk_available(provider), "key": key_present(provider)}


# --- extraction prompt ---

EXTRACTION_FIELDS = """
Return a single JSON object (no prose, no markdown fences) shaped as:
{
  "profile": {
    "pcn_number": str|null, "rcn_number": str|null, "job_number": str|null,
    "licensee": str|null, "call_sign": str|null, "radio_service": str|null,
    "station_class": str|null, "frequency_band": one of
      ["6 GHz","11 GHz","18 GHz","23 GHz","70/80 GHz","90 GHz"]|null,
    "channel_plan_mhz": number|null, "path_length_km": number|null,
    "path_length_miles": number|null, "atmospheric_loss_db": number|null,
    "free_space_loss_db": number|null, "receiver_threshold_dbm": number|null
  },
  "endpoints": [
    { "side": "A"|"Z", "pcn_site_name": str|null, "county_state": str|null,
      "latitude": number|null, "longitude": number|null,
      "tx_frequency_mhz": number|null, "antenna_model": str|null,
      "antenna_gain_dbi": number|null, "path_azimuth_deg": number|null,
      "radio_model": str|null, "polarization": str|null }
  ],
  "modulation_targets": [
    { "direction": "A_TO_Z"|"Z_TO_A",
      "modulation": one of ["4096 QAM","2048 QAM","1024 QAM","512 QAM",
        "256 QAM","128 QAM","64 QAM","32 QAM","16 QAM","QPSK","BPSK"],
      "data_rate_kbps": integer|null, "max_power_dbm": number|null,
      "eirp_dbm": number|null, "expected_rsl_dbm": number|null,
      "emission_designator": str|null, "radio_model": str|null }
  ]
}
Use null for anything not present. Side A is the first/primary site, side Z the
far end. Do not invent values.
""".strip()


def build_prompt(override=None):
    base = (
        "You are extracting licensed microwave/mmWave link engineering data from "
        "a PCN (Prior Coordination Notice) PDF for import into NetBox.\n\n"
        + EXTRACTION_FIELDS
    )
    if override:
        base += "\n\nAdditional guidance:\n" + override
    return base


def parse_json_response(text):
    """Extract a JSON object from a model response, tolerating code fences."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip().strip("`").strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("No JSON object found in model response")
    return json.loads(text[start:end + 1])


# --- adapter registry + failover ---

ADAPTERS = {}


def register_adapter(provider, fn):
    ADAPTERS[provider] = fn


def extraction_chain():
    from .models import WirelessLLMProvider

    return list(
        WirelessLLMProvider.objects.filter(enabled=True).order_by("rank", "provider")
    )


def _format_attempts(attempts):
    return "; ".join(f"{p}/{m}: {why}" for p, m, why in attempts)


def extract_from_pdf(pdf_bytes, *, prompt=None, chain=None, adapters=None, key_getter=None):
    """
    Walk the provider chain and return the first successful ExtractionResult.

    Pure/injectable for testing: pass ``chain`` (objects with ``.provider`` /
    ``.model``), ``adapters`` (provider -> callable), and ``key_getter``.
    Raises :class:`ProviderError` (with per-attempt reasons) if all fail.
    """
    chain = chain if chain is not None else extraction_chain()
    adapters = adapters if adapters is not None else ADAPTERS
    key_getter = key_getter or get_api_key
    prompt = prompt if prompt is not None else build_prompt()

    attempts = []
    for entry in chain:
        provider, model = entry.provider, entry.model
        adapter = adapters.get(provider)
        if adapter is None:
            attempts.append((provider, model, "SDK not installed / no adapter"))
            continue
        api_key = key_getter(provider)
        if not api_key:
            attempts.append((provider, model, "no API key configured"))
            continue
        try:
            data = adapter(pdf_bytes, model, api_key, prompt)
            return ExtractionResult(provider, model, data, attempts)
        except Exception as exc:
            logger.warning("LLM provider %s/%s failed: %s", provider, model, exc)
            attempts.append((provider, model, str(exc)))
            continue
    raise ProviderError(
        "All configured LLM providers failed: " + (_format_attempts(attempts) or "chain empty")
    )


# --- per-vendor adapters (thin, lazy-imported, optional) ---

def _anthropic_adapter(pdf_bytes, model, api_key, prompt):
    import base64

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{
            "role": "user",
            "content": [
                {"type": "document", "source": {
                    "type": "base64", "media_type": "application/pdf",
                    "data": base64.standard_b64encode(pdf_bytes).decode(),
                }},
                {"type": "text", "text": prompt},
            ],
        }],
    )
    return parse_json_response("".join(b.text for b in message.content if b.type == "text"))


def _gemini_adapter(pdf_bytes, model, api_key, prompt):
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=[
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            prompt,
        ],
    )
    return parse_json_response(response.text)


def _openai_adapter(pdf_bytes, model, api_key, prompt):
    import base64

    from openai import OpenAI

    client = OpenAI(api_key=api_key)
    b64 = base64.standard_b64encode(pdf_bytes).decode()
    response = client.responses.create(
        model=model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_file", "filename": "pcn.pdf",
                 "file_data": f"data:application/pdf;base64,{b64}"},
                {"type": "input_text", "text": prompt},
            ],
        }],
    )
    return parse_json_response(response.output_text)


def _register_default_adapters():
    for provider, fn in (
        ("anthropic", _anthropic_adapter),
        ("gemini", _gemini_adapter),
        ("openai", _openai_adapter),
    ):
        if sdk_available(provider):
            register_adapter(provider, fn)


_register_default_adapters()
