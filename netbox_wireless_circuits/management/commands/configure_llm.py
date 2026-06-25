"""
Interactive setup for the optional PCN-PDF LLM importer.

    sudo /opt/netbox/venv/bin/python /opt/netbox/netbox/manage.py configure_llm

Walks you through picking a provider, model, and rank; prompts (silently) for
the API key; writes the key to the environment file that systemd loads (keys are
NEVER stored in NetBox's database); upserts the provider row in the fallback
chain; enables PCN-PDF import; and offers to restart NetBox.

Run it with ``sudo`` so it can write the root-owned env file and restart the
service. Non-interactive use is supported via flags (see ``--help``); the key
may also be supplied on stdin to keep it out of the process arguments.
"""
import getpass
import os
import subprocess
import sys
import tempfile

from django.core.management.base import BaseCommand, CommandError

from netbox_wireless_circuits.choices import LLMProviderChoices
from netbox_wireless_circuits.llm import ENV_KEYS, sdk_available
from netbox_wireless_circuits.models import WirelessLLMProvider, WirelessLLMSettings

# Must match the EnvironmentFile path referenced by the systemd drop-in
# (/etc/systemd/system/netbox.service.d/llm.conf).
DEFAULT_ENV_FILE = "/etc/netbox-wireless-llm.env"

# Sensible, cheap-and-capable starting points for PDF OCR/extraction. The
# operator can override with anything from "Available LLM Models".
DEFAULT_MODELS = {
    "anthropic": "claude-haiku-4-5",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4.1",
}

RESTART_SERVICES = ("netbox", "netbox-rq")


def merge_env_file(content, var_name, value):
    """
    Return ``content`` with ``VAR_NAME=value`` set, preserving every other line.

    Pure (no I/O) so it is unit-testable. An existing assignment to the same
    variable is replaced in place; otherwise the assignment is appended. Other
    providers' keys, comments, and blank lines are left untouched.
    """
    lines = content.splitlines()
    new_line = f"{var_name}={value}"
    replaced = False
    out = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            name = stripped.split("=", 1)[0].strip()
            if name == var_name:
                out.append(new_line)
                replaced = True
                continue
        out.append(line)
    if not replaced:
        out.append(new_line)
    return "\n".join(out).rstrip("\n") + "\n"


def write_env_file(path, var_name, value):
    """Atomically merge ``var_name=value`` into ``path`` with 0600 perms."""
    existing = ""
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            existing = fh.read()
    merged = merge_env_file(existing, var_name, value)
    directory = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".llm-env-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(merged)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class Command(BaseCommand):
    help = "Interactively configure the optional PCN-PDF LLM importer (provider, model, key)."

    def add_arguments(self, parser):
        parser.add_argument("--provider", choices=[c[0] for c in LLMProviderChoices.CHOICES],
                            help="Provider key (anthropic|gemini|openai); prompts if omitted.")
        parser.add_argument("--model", help="Model identifier; prompts (with a default) if omitted.")
        parser.add_argument("--rank", type=int, help="Chain rank (1 = primary); prompts if omitted.")
        parser.add_argument("--key-stdin", action="store_true",
                            help="Read the API key from stdin instead of an interactive prompt.")
        parser.add_argument("--env-file", default=DEFAULT_ENV_FILE,
                            help=f"Path of the env file systemd loads (default {DEFAULT_ENV_FILE}).")
        parser.add_argument("--enable-import", dest="enable_import", action="store_true", default=None,
                            help="Turn on PCN-PDF import without asking.")
        parser.add_argument("--no-enable-import", dest="enable_import", action="store_false",
                            help="Leave PCN-PDF import setting unchanged.")
        parser.add_argument("--restart", dest="restart", action="store_true", default=None,
                            help="Restart NetBox afterwards without asking.")
        parser.add_argument("--no-restart", dest="restart", action="store_false",
                            help="Do not restart NetBox.")
        parser.add_argument("--no-input", action="store_true",
                            help="Fail instead of prompting (for automation).")

    # --- small interaction helpers ---

    def _prompt(self, label, default=None, no_input=False):
        if no_input:
            if default is None:
                raise CommandError(f"--no-input set but no value for '{label}'.")
            return default
        suffix = f" [{default}]" if default else ""
        ans = input(f"{label}{suffix}: ").strip()
        return ans or (default or "")

    def _confirm(self, label, default=True, no_input=False):
        if no_input:
            return default
        d = "Y/n" if default else "y/N"
        ans = input(f"{label} [{d}]: ").strip().lower()
        if not ans:
            return default
        return ans in ("y", "yes")

    def handle(self, *args, **options):
        no_input = options["no_input"]
        out = self.stdout

        out.write(self.style.MIGRATE_HEADING("Configure the PCN-PDF LLM importer"))
        out.write("API keys are written to the server environment file and NEVER stored in NetBox.\n")

        # 1) provider
        provider = options["provider"]
        if not provider:
            choices = LLMProviderChoices.CHOICES
            out.write("Which LLM provider?")
            for i, (key, label, _color) in enumerate(choices, 1):
                sdk = "SDK installed" if sdk_available(key) else "SDK NOT installed"
                out.write(f"  {i}) {label}  ({key}, {sdk})")
            sel = self._prompt("Choose 1-%d" % len(choices), default="1", no_input=no_input)
            try:
                provider = choices[int(sel) - 1][0]
            except (ValueError, IndexError):
                raise CommandError(f"Invalid selection: {sel!r}")

        if not sdk_available(provider):
            out.write(self.style.WARNING(
                f"\nNote: the {provider} SDK is not installed in this environment. "
                f"Install it with: pip install netbox-wireless-circuits[llm]\n"
                "Configuration will still be saved."
            ))

        # 2) model
        model = options["model"] or self._prompt(
            "Model identifier (see 'Available LLM Models' for live IDs)",
            default=DEFAULT_MODELS.get(provider, ""), no_input=no_input,
        )
        if not model:
            raise CommandError("A model identifier is required.")

        # 3) rank
        rank_opt = options["rank"]
        if rank_opt is None:
            rank_opt = int(self._prompt("Rank (1 = tried first)", default="1", no_input=no_input))

        # 4) API key (silent; blank keeps any existing key)
        env_var = ENV_KEYS.get(provider)
        if options["key_stdin"]:
            key = sys.stdin.readline().rstrip("\n")
        elif no_input:
            key = ""  # rely on a key already present in the env / PLUGINS_CONFIG
        else:
            key = getpass.getpass(
                f"{env_var} (paste the API key; leave blank to keep the current one): "
            )

        # --- apply: env file ---
        env_file = options["env_file"]
        if key:
            try:
                write_env_file(env_file, env_var, key)
            except PermissionError:
                raise CommandError(
                    f"Cannot write {env_file} (permission denied). Re-run this command with "
                    f"sudo, or set the key yourself:\n"
                    f"  printf '{env_var}=%s\\n' 'YOUR_KEY' | sudo tee -a {env_file} >/dev/null && "
                    f"sudo chmod 600 {env_file}"
                )
            out.write(self.style.SUCCESS(f"Wrote {env_var} to {env_file} (mode 600)."))
            del key  # don't keep the secret around
        else:
            out.write(f"No key entered — leaving {env_var} as-is in {env_file}.")

        # --- apply: provider row + import toggle (DB) ---
        obj, created = WirelessLLMProvider.objects.update_or_create(
            provider=provider, model=model, defaults={"rank": rank_opt, "enabled": True},
        )
        out.write(self.style.SUCCESS(
            f"{'Created' if created else 'Updated'} provider row: {obj}"
        ))

        enable_import = options["enable_import"]
        if enable_import is None:
            enable_import = self._confirm(
                "Enable PCN-PDF import now?", default=True, no_input=no_input
            )
        if enable_import:
            settings = WirelessLLMSettings.load()
            if not settings.pdf_import_enabled:
                settings.pdf_import_enabled = True
                settings.save()
            out.write(self.style.SUCCESS("PCN-PDF import is enabled."))

        # --- restart ---
        restart = options["restart"]
        if restart is None:
            restart = self._confirm(
                "Restart NetBox now so the key takes effect?", default=True, no_input=no_input
            )
        if restart:
            self._restart(out)
        else:
            out.write(self.style.WARNING(
                "Restart skipped. The new key loads on the next restart:\n"
                f"  sudo systemctl restart {' '.join(RESTART_SERVICES)}"
            ))

        out.write(self.style.SUCCESS("\nDone. Try it: Circuits → Wireless Circuits → Import from PCN PDF."))

    def _restart(self, out):
        if os.geteuid() != 0:
            out.write(self.style.WARNING(
                "Not running as root; cannot restart the service directly. Run:\n"
                f"  sudo systemctl restart {' '.join(RESTART_SERVICES)}"
            ))
            return
        for svc in RESTART_SERVICES:
            try:
                subprocess.run(["systemctl", "restart", svc], check=True)
                out.write(self.style.SUCCESS(f"Restarted {svc}."))
            except subprocess.CalledProcessError:
                # netbox-rq may not exist on every install; report and move on.
                out.write(self.style.WARNING(f"Could not restart {svc} (may not be installed)."))
            except FileNotFoundError:
                out.write(self.style.WARNING("systemctl not found; restart NetBox manually."))
                return
