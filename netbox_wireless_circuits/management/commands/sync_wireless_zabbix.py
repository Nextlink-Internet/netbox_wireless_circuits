"""
Backfill / full reconcile of wireless link design intent into nbxsync macros
and tags. Run after enabling the sync or importing the Zabbix wireless template.

    python manage.py sync_wireless_zabbix
"""
from django.core.management.base import BaseCommand

from netbox_wireless_circuits.models import WirelessGlobalSettings
from netbox_wireless_circuits.nbxsync_sync import (
    nbxsync_available,
    resync_all,
    sync_enabled,
)


class Command(BaseCommand):
    help = "Reconcile wireless link expected values into nbxsync Zabbix macros/tags."

    def handle(self, *args, **options):
        if not nbxsync_available():
            self.stderr.write(self.style.ERROR(
                "nbxsync is not installed; nothing to sync."
            ))
            return

        settings = WirelessGlobalSettings.load()
        if not sync_enabled(settings):
            self.stderr.write(self.style.WARNING(
                "Zabbix macro sync is disabled in Wireless Global Settings "
                "(zabbix_sync_enabled is off). Enable it and re-run."
            ))
            return

        results = resync_all(settings)
        if not results:
            self.stdout.write("No devices terminate a wireless endpoint; nothing to do.")
            return

        missing = set()
        macros = tags = deleted = 0
        for r in results:
            macros += r["macros_written"]
            tags += r["tags_written"]
            deleted += r["macros_deleted"] + r["tags_deleted"]
            missing.update(r["macros_missing_def"])

        self.stdout.write(self.style.SUCCESS(
            f"Synced {len(results)} device(s): {macros} macro assignment(s), "
            f"{tags} tag assignment(s), {deleted} stale removed."
        ))
        if missing:
            self.stdout.write(self.style.WARNING(
                "Missing macro definitions (define these in your Zabbix wireless "
                "template and import it into nbxsync): " + ", ".join(sorted(missing))
            ))
