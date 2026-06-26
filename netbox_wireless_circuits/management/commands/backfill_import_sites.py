"""
Backfill NetBox Site links (and native A/Z circuit terminations) onto already
imported wireless endpoints, by matching each endpoint's ``pcn_site_name`` to a
NetBox Site name (normalized). Useful because the CSV importer's re-upload policy
reports existing links rather than modifying them, so site links added after the
initial import (or matched by a later fix) won't apply on re-upload.

    python manage.py backfill_import_sites --source comsearch
    python manage.py backfill_import_sites --source comsearch --dry-run
"""
from django.core.management.base import BaseCommand

from netbox_wireless_circuits import pcn_import
from netbox_wireless_circuits.importers.engine import (
    _load_site_map,
    _normalize_site_name,
)
from netbox_wireless_circuits.models import WirelessCircuitEndpoint


class Command(BaseCommand):
    help = "Link imported endpoints to NetBox Sites by name and create terminations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source", default="comsearch",
            help="Only backfill links from this import source (default: comsearch).",
        )
        parser.add_argument(
            "--dry-run", action="store_true",
            help="Report what would be linked without writing.",
        )

    def handle(self, *args, **options):
        site_map = _load_site_map()
        endpoints = (
            WirelessCircuitEndpoint.objects
            .filter(
                wireless_license_profile__import_source=options["source"],
                netbox_site__isnull=True,
            )
            .exclude(pcn_site_name="")
            .select_related("wireless_license_profile__circuit")
        )

        linked = unmatched = 0
        for ep in endpoints.iterator():
            site = site_map.get(_normalize_site_name(ep.pcn_site_name))
            if site is None:
                unmatched += 1
                continue
            linked += 1
            if not options["dry_run"]:
                ep.netbox_site = site
                ep.save(update_fields=["netbox_site"])
                pcn_import.ensure_circuit_termination(
                    ep.wireless_license_profile.circuit, ep.side, site
                )

        verb = "would link" if options["dry_run"] else "linked"
        self.stdout.write(self.style.SUCCESS(
            f"{options['source']}: {verb} {linked} endpoint(s) to sites; "
            f"{unmatched} unmatched (no NetBox site with that name)."
        ))
