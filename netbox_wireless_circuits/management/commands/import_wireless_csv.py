"""
Bulk-import a coordinator CSV export from the command line (the same engine the
web importer uses, run synchronously). Useful for the initial large load and for
scheduled re-syncs.

    python manage.py import_wireless_csv --source comsearch \
        --provider "Comsearch" --type "Licensed Microwave" path/to/export.csv

New links are created; links already present are reported (not modified).
"""
from django.core.management.base import BaseCommand, CommandError

from circuits.models import CircuitType, Provider

from netbox_wireless_circuits.importers import all_sources, get_source
from netbox_wireless_circuits.importers.engine import run_import


class Command(BaseCommand):
    help = "Import a coordinator wireless-links CSV export (e.g. Comsearch)."

    def add_arguments(self, parser):
        parser.add_argument("csv_file", help="Path to the CSV export.")
        parser.add_argument(
            "--source", required=True,
            help="Import source name (e.g. 'comsearch'). "
                 f"Available: {', '.join(s.name for s in all_sources())}.",
        )
        parser.add_argument("--provider", required=True, help="Provider name.")
        parser.add_argument(
            "--type", default=None,
            help="Circuit type name. Omit to use the source's default "
                 "(e.g. Comsearch -> 'Licensed Microwave', created if needed).",
        )
        parser.add_argument(
            "--status", default="active",
            help="Fallback circuit status; status is otherwise derived from each "
                 "link's FCC license status (default fallback: active).",
        )

    def handle(self, *args, **options):
        source = get_source(options["source"])
        if source is None:
            raise CommandError(
                f"Unknown source {options['source']!r}. Available: "
                f"{', '.join(s.name for s in all_sources())}."
            )
        try:
            provider = Provider.objects.get(name=options["provider"])
        except Provider.DoesNotExist:
            raise CommandError(f"Provider {options['provider']!r} not found.")
        circuit_type = None
        if options["type"]:
            try:
                circuit_type = CircuitType.objects.get(name=options["type"])
            except CircuitType.DoesNotExist:
                raise CommandError(f"Circuit type {options['type']!r} not found.")

        with open(options["csv_file"], "rb") as fh:
            report = run_import(
                source, fh,
                provider=provider, circuit_type=circuit_type,
                status=options["status"],
            )

        self.stdout.write(self.style.SUCCESS(
            f"{report['source']}: {report['total']} link(s) — "
            f"{len(report['created'])} created, {len(report['changed'])} changed, "
            f"{report['unchanged']} unchanged, {len(report['errors'])} error(s)."
        ))
        self.stdout.write(
            f"  sites: {report.get('sites_linked', 0)} linked, "
            f"{report.get('sites_unmatched', 0)} unmatched (left blank)."
        )
        for ch in report["changed"]:
            self.stdout.write(f"  changed: {ch['cid']} ({len(ch['changes'])} field(s))")
        for err in report["errors"]:
            self.stdout.write(self.style.WARNING(f"  error: {err['cid']}: {err['error']}"))
