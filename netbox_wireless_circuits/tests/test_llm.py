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

    def test_requires_full_modulation_ladder(self):
        # The prompt must tell the model to return every modulation step, both
        # directions — not just the top (4096 QAM) row.
        p = build_prompt()
        self.assertIn("ADAPTIVE MODULATION LADDER", p)
        self.assertIn("EVERY row", p)


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


class MergeEnvFileTests(SimpleTestCase):
    def _merge(self, *args):
        from netbox_wireless_circuits.management.commands.configure_llm import merge_env_file

        return merge_env_file(*args)

    def test_adds_to_empty(self):
        self.assertEqual(self._merge("", "OPENAI_API_KEY", "sk-1"), "OPENAI_API_KEY=sk-1\n")

    def test_replaces_existing_in_place(self):
        out = self._merge("OPENAI_API_KEY=old\n", "OPENAI_API_KEY", "new")
        self.assertEqual(out, "OPENAI_API_KEY=new\n")

    def test_preserves_other_keys_and_comments(self):
        src = "# secrets\nANTHROPIC_API_KEY=a\nGEMINI_API_KEY=g\n"
        out = self._merge(src, "OPENAI_API_KEY", "o")
        self.assertIn("ANTHROPIC_API_KEY=a", out)
        self.assertIn("GEMINI_API_KEY=g", out)
        self.assertIn("# secrets", out)
        self.assertIn("OPENAI_API_KEY=o", out)

    def test_replaces_only_target_key(self):
        src = "ANTHROPIC_API_KEY=a\nOPENAI_API_KEY=old\n"
        out = self._merge(src, "OPENAI_API_KEY", "new")
        self.assertIn("ANTHROPIC_API_KEY=a", out)
        self.assertIn("OPENAI_API_KEY=new", out)
        self.assertNotIn("old", out)


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
