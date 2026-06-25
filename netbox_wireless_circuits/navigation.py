"""
Navigation for netbox_wireless_circuits.

Rather than registering a standalone top-level plugin menu (which NetBox renders
in its own block below the core menus), we inject a "Wireless Circuits" group
into NetBox's core **Circuits** menu so the links sit alongside the native
circuit entries.

NOTE: NetBox provides no supported API for placing a plugin menu among the core
menus, so this reaches into ``netbox.navigation.menu.MENUS``. It is written
defensively (best-effort, never breaks startup) and may need revisiting on a
future NetBox upgrade.
"""
import logging

from django.utils.translation import gettext_lazy as _

from netbox.navigation import MenuGroup, MenuItem, MenuItemButton

logger = logging.getLogger("netbox_wireless_circuits")

PLUGIN = "netbox_wireless_circuits"


def _button(model, action, title, icon):
    return MenuItemButton(
        link=f"plugins:{PLUGIN}:{model}_{action}",
        title=title,
        icon_class=icon,
        permissions=[f"{PLUGIN}.add_{model}"],
    )


def _item(model, label, *, with_import):
    buttons = [_button(model, "add", _("Add"), "mdi mdi-plus-thick")]
    if with_import:
        buttons.append(_button(model, "import", _("Import"), "mdi mdi-upload"))
    return MenuItem(
        link=f"plugins:{PLUGIN}:{model}_list",
        link_text=label,
        permissions=[f"{PLUGIN}.view_{model}"],
        buttons=tuple(buttons),
    )


wireless_circuits_group = MenuGroup(
    label=_("Wireless Circuits"),
    items=(
        _item("wirelesslicenseprofile", _("Wireless License Profiles"), with_import=True),
        MenuItem(
            link=f"plugins:{PLUGIN}:pcn_import",
            link_text=_("Import from PCN PDF"),
            permissions=[f"{PLUGIN}.add_wirelesslicenseprofile"],
        ),
        _item("wirelesscircuitendpoint", _("Wireless Circuit Endpoints"), with_import=False),
        _item("wirelessmodulationtarget", _("Wireless Modulation Targets"), with_import=True),
        _item("wirelesstargetexception", _("Target Exceptions"), with_import=False),
        _item("wirelessllmprovider", _("LLM Providers"), with_import=False),
        MenuItem(
            link=f"plugins:{PLUGIN}:wirelessllmsettings",
            link_text=_("LLM Settings"),
            permissions=[f"{PLUGIN}.change_wirelessllmsettings"],
        ),
        MenuItem(
            link=f"plugins:{PLUGIN}:wirelessglobalsettings",
            link_text=_("Global Settings"),
            permissions=[f"{PLUGIN}.change_wirelessglobalsettings"],
        ),
    ),
)


def inject_into_circuits_menu():
    """Append our group to the core Circuits menu. Best-effort and idempotent."""
    try:
        from netbox.navigation.menu import MENUS

        for menu in MENUS:
            if str(getattr(menu, "label", "")) == "Circuits":
                if wireless_circuits_group not in menu.groups:
                    menu.groups = (*menu.groups, wireless_circuits_group)
                return True
        logger.warning("netbox_wireless_circuits: core 'Circuits' menu not found; "
                       "wireless menu not injected.")
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("netbox_wireless_circuits: could not inject Circuits menu: %s", exc)
    return False
