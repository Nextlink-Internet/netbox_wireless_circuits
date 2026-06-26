"""
Source-aware bulk CSV import for wireless links.

The web importer lets an operator pick an **import type** (PCN PDF or CSV) and,
for CSV, a **data source** (Comsearch today; other coordinators later, each with
its own column layout). Every source adapter parses its own columns and emits the
same canonical structure (``{profile, endpoints[], modulation_targets[]}``), which
a single shared engine (:mod:`.engine`) upserts/diffs onto the plugin models.

Adding a new CSV source = add one :class:`~.base.BaseCSVSource` subclass and
register it; the engine, job, views, and templates are source-agnostic.
"""
from .base import BaseCSVSource, ParsedLink, register_source, get_source, all_sources
from . import comsearch  # noqa: F401  (registers the Comsearch adapter on import)

__all__ = (
    "BaseCSVSource",
    "ParsedLink",
    "register_source",
    "get_source",
    "all_sources",
)
