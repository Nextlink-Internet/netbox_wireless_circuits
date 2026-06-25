"""
Auto-apply a NetBox tag reflecting a wireless link's N+0 radio configuration.

The tag name comes from an operator-configurable template (default
``"link_type: {config}"``) where ``{config}`` is the profile's
``radio_configuration`` (e.g. ``2+0``). Pure helpers + one apply function so the
behaviour is unit-testable; it is invoked from the profile post_save signal so a
created or edited profile keeps its circuit's link-type tag in sync.
"""
import re

from django.utils.text import slugify

# Matches a carrier-aggregation config like 1+0, 2+0, 4+0, 1+1.
_CONFIG_RE = r"\d+\+\d+"
PLACEHOLDER = "{config}"


def tag_name(template, config):
    """Render the tag name from the template and a config string."""
    return (template or PLACEHOLDER).replace(PLACEHOLDER, config)


def _generated_tag_matcher(template):
    """
    Regex matching any tag name this template could have produced (for any
    N+0 config), so stale link-type tags can be removed when the config changes.
    """
    parts = (template or PLACEHOLDER).split(PLACEHOLDER)
    pattern = _CONFIG_RE.join(re.escape(p) for p in parts)
    return re.compile("^" + pattern + "$")


def apply_link_type_tag(circuit, profile, settings):
    """
    Sync the circuit's link-type NetBox tag to ``profile.radio_configuration``.

    Removes any previously-generated link-type tags (those the template could
    have produced) so a changed config doesn't leave the old tag behind, then
    applies the current one. No-op when disabled, when there's no circuit, or
    when the profile has no radio_configuration. Returns the applied Tag or None.
    """
    if circuit is None or not getattr(settings, "link_type_tag_enabled", False):
        return None

    from extras.models import Tag

    template = settings.link_type_tag_template or PLACEHOLDER
    config = (profile.radio_configuration or "").strip()
    desired = tag_name(template, config) if config else None
    matcher = _generated_tag_matcher(template)

    stale = [
        t for t in circuit.tags.all()
        if matcher.match(t.name) and t.name != desired
    ]
    if stale:
        circuit.tags.remove(*stale)

    if not desired:
        return None
    slug = slugify(desired) or slugify("link-type-" + config) or "link-type"
    tag, _ = Tag.objects.get_or_create(slug=slug, defaults={"name": desired})
    circuit.tags.add(tag)
    return tag
