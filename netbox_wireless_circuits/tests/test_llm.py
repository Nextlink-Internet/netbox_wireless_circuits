from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from netbox_wireless_circuits.llm import (
    ProviderError,
    build_prompt,
    discover_models,
    extract_from_pdf,
    get_api_key,
    parse_json_response,
)


def entry(provider, model="m"):
    return SimpleNamespace(provider=provider, model=model)


class ParseJsonTests(SimpleTestCase):
    def test_plain(self):
        self.assertEqual(parse_json_response('{"a": 1}'), {"a": 1})

    def test_fenced(self):
        self.assertEqual(parse_json_response('```json\n{"a": 1}\n```'), {"a": 1})

    def test_surrounding_prose(self):
        self.assertEqual(
            parse_json_response('Here you go:\n{"a": 1}\nThanks!'), {"a": 1}
        )

    def test_no_json_raises(self):
        with self.assertRaises(ValueError):
            parse_json_response("no json here")


class PromptTests(SimpleTestCase):
    def test_includes_override(self):
        p = build_prompt("watch the footer table")
        self.assertIn("watch the footer table", p)
        self.assertIn("modulation_targets", p)


class KeyResolutionTests(SimpleTestCase):
    def test_env_fallback(self):
        with mock.patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}, clear=False):
            self.assertEqual(get_api_key("anthropic"), "sk-test")

    def test_missing_key_none(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(get_api_key("openai"))


class DiscoverModelsTests(SimpleTestCase):
    def test_reports_each_provider_without_raising(self):
        results = discover_models()
        providers = {r["provider"] for r in results}
        self.assertEqual(providers, {"anthropic", "gemini", "openai"})
        for r in results:
            # Never raises; entries are well-formed regardless of SDK/key presence.
            self.assertIn("sdk", r)
            self.assertIn("key", r)
            self.assertIsInstance(r["models"], list)
            # A provider without SDK or key is not queried (no error, no models).
            if not (r["sdk"] and r["key"]):
                self.assertIsNone(r["error"])
                self.assertEqual(r["models"], [])


class FailoverTests(SimpleTestCase):
    PDF = b"%PDF-1.7 fake"

    def _keys(self, present):
        return lambda provider: "key" if provider in present else None

    def test_first_succeeds(self):
        adapters = {"anthropic": lambda *a: {"ok": "a"}, "gemini": lambda *a: {"ok": "g"}}
        result = extract_from_pdf(
            self.PDF, chain=[entry("anthropic"), entry("gemini")],
            adapters=adapters, key_getter=self._keys({"anthropic", "gemini"}),
        )
        self.assertEqual(result.provider, "anthropic")
        self.assertEqual(result.data, {"ok": "a"})

    def test_falls_through_on_error(self):
        def boom(*a):
            raise RuntimeError("rate limited")

        adapters = {"anthropic": boom, "gemini": lambda *a: {"ok": "g"}}
        result = extract_from_pdf(
            self.PDF, chain=[entry("anthropic"), entry("gemini")],
            adapters=adapters, key_getter=self._keys({"anthropic", "gemini"}),
        )
        self.assertEqual(result.provider, "gemini")
        self.assertEqual(len(result.attempts), 1)
        self.assertIn("rate limited", result.attempts[0][2])

    def test_skips_provider_without_key(self):
        adapters = {"anthropic": lambda *a: {"ok": "a"}, "openai": lambda *a: {"ok": "o"}}
        result = extract_from_pdf(
            self.PDF, chain=[entry("anthropic"), entry("openai")],
            adapters=adapters, key_getter=self._keys({"openai"}),
        )
        self.assertEqual(result.provider, "openai")
        self.assertIn("no API key", result.attempts[0][2])

    def test_skips_provider_without_adapter(self):
        adapters = {"openai": lambda *a: {"ok": "o"}}  # gemini has no adapter
        result = extract_from_pdf(
            self.PDF, chain=[entry("gemini"), entry("openai")],
            adapters=adapters, key_getter=self._keys({"gemini", "openai"}),
        )
        self.assertEqual(result.provider, "openai")

    def test_all_fail_raises(self):
        def boom(*a):
            raise RuntimeError("nope")

        with self.assertRaises(ProviderError) as cm:
            extract_from_pdf(
                self.PDF, chain=[entry("anthropic"), entry("gemini")],
                adapters={"anthropic": boom, "gemini": boom},
                key_getter=self._keys({"anthropic", "gemini"}),
            )
        self.assertIn("anthropic", str(cm.exception))
        self.assertIn("gemini", str(cm.exception))

    def test_empty_chain_raises(self):
        with self.assertRaises(ProviderError):
            extract_from_pdf(self.PDF, chain=[], adapters={}, key_getter=self._keys(set()))
