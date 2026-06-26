"""
Background job that runs a CSV import off the request thread.

A full coordinator export is thousands of links (each → a circuit + profile +
two endpoints + modulation targets), which would exceed web-request timeouts. The
import view stashes the uploaded file and enqueues this job; netbox-rq runs it and
the result report is stored on the Job (visible on the job's detail page).
"""
import io
import logging

from django.core.files.storage import default_storage
from netbox.jobs import JobRunner

from .base import get_source
from .engine import run_import

logger = logging.getLogger("netbox_wireless_circuits")


class WirelessCSVImportJob(JobRunner):

    class Meta:
        name = "Wireless CSV import"

    # A full coordinator export is thousands of links — well beyond the 300s RQ
    # default (RQ_DEFAULT_TIMEOUT). Allow an hour. If it ever still times out,
    # re-queueing resumes cleanly: already-created links are skipped by their
    # (import_source, import_key) de-dup key, so only the remainder is created.
    job_timeout = 60 * 60

    def run(self, *args, source_name=None, file_name=None, provider_id=None,
            circuit_type_id=None, status="active", apply_changes=False, **kwargs):
        from circuits.models import CircuitType, Provider

        source = get_source(source_name)
        if source is None:
            raise ValueError(f"Unknown import source: {source_name!r}")
        provider = Provider.objects.get(pk=provider_id)
        # None -> the engine get-or-creates the source's default circuit type.
        circuit_type = (
            CircuitType.objects.get(pk=circuit_type_id) if circuit_type_id else None
        )

        # The upload lives in MEDIA storage (shared with the web process). Read
        # it fully here so we can log the byte count (diagnostics) and feed a
        # stable buffer to the importer.
        exists = default_storage.exists(file_name)
        size = default_storage.size(file_name) if exists else -1
        logger.info(
            "wireless CSV import: reading %s (exists=%s, size=%s bytes)",
            file_name, exists, size,
        )
        with default_storage.open(file_name, "rb") as fh:
            raw = fh.read()
        logger.info("wireless CSV import: %d bytes read from %s", len(raw), file_name)

        report = run_import(
            source, io.BytesIO(raw),
            provider=provider, circuit_type=circuit_type, status=status,
            apply_changes=apply_changes,
            progress=self._progress,
        )

        if report["total"] == 0:
            # Nothing parsed — keep the file for inspection and log a sample.
            logger.warning(
                "wireless CSV import: 0 rows parsed from %s (%d bytes). head=%r",
                file_name, len(raw), raw[:300],
            )
        else:
            try:
                default_storage.delete(file_name)
            except Exception:  # pragma: no cover - best-effort cleanup
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
