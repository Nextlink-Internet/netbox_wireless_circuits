"""
Background job that runs a CSV import off the request thread.

A full coordinator export is thousands of links (each → a circuit + profile +
two endpoints + modulation targets), which would exceed web-request timeouts. The
import view stashes the uploaded file and enqueues this job; netbox-rq runs it and
the result report is stored on the Job (visible on the job's detail page).
"""
import logging
import os

from netbox.jobs import JobRunner

from .base import get_source
from .engine import run_import

logger = logging.getLogger("netbox_wireless_circuits")


class WirelessCSVImportJob(JobRunner):

    class Meta:
        name = "Wireless CSV import"

    def run(self, *args, source_name=None, file_path=None, provider_id=None,
            circuit_type_id=None, status="active", apply_changes=False, **kwargs):
        from circuits.models import CircuitType, Provider

        source = get_source(source_name)
        if source is None:
            raise ValueError(f"Unknown import source: {source_name!r}")
        provider = Provider.objects.get(pk=provider_id)
        circuit_type = CircuitType.objects.get(pk=circuit_type_id)

        try:
            with open(file_path, "rb") as fh:
                report = run_import(
                    source, fh,
                    provider=provider, circuit_type=circuit_type, status=status,
                    apply_changes=apply_changes,
                    progress=self._progress,
                )
        finally:
            try:
                os.unlink(file_path)
            except OSError:
                pass

        # Persist a compact result summary on the job for the detail page.
        self.job.data = {
            "summary": {
                "source": report["source"],
                "total": report["total"],
                "created": len(report["created"]),
                "changed": len(report["changed"]),
                "unchanged": report["unchanged"],
                "errors": len(report["errors"]),
            },
            "report": report,
        }
        self.job.save()
        logger.info(
            "wireless CSV import (%s): %d total, %d created, %d changed, "
            "%d unchanged, %d errors",
            report["source"], report["total"], len(report["created"]),
            len(report["changed"]), report["unchanged"], len(report["errors"]),
        )
        return report

    def _progress(self, n):
        logger.debug("wireless CSV import: %d links processed", n)
