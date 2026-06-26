"""
Navigation for netbox_wireless_circuits.

Uses NetBox's supported plugin-menu API (``PluginMenu``), which renders a
"Wireless Circuits" menu in the plugins navigation section. This is stable
across NetBox releases — earlier versions of this plugin injected a group into
the core Circuits menu via an unsupported internal API (``netbox.navigation.
menu.MENUS``) that NetBox 4.6 removed, so the menu is now registered the
official way.
"""
from netbox.plugins import PluginMenu, PluginMenuButton, PluginMenuItem

PLUGIN = "netbox_wireless_circuits"


def _button(model, action, title, icon):
    return PluginMenuButton(
        link=f"plugins:{PLUGIN}:{model}_{action}",
        title=title,
        icon_class=icon,
        permissions=[f"{PLUGIN}.add_{model}"],
    )


def _item(model, label, *, with_import=False):
    buttons = [_button(model, "add", "Add", "mdi mdi-plus-thick")]
    if with_import:
        buttons.append(_button(model, "import", "Import", "mdi mdi-upload"))
    return PluginMenuItem(
        link=f"plugins:{PLUGIN}:{model}_list",
        link_text=label,
        permissions=[f"{PLUGIN}.view_{model}"],
        buttons=tuple(buttons),
    )


def _plain(url_name, label, perm):
    return PluginMenuItem(
        link=f"plugins:{PLUGIN}:{url_name}",
        link_text=label,
        permissions=[f"{PLUGIN}.{perm}"],
    )


menu = PluginMenu(
    label="Wireless Circuits",
    icon_class="mdi mdi-radio-tower",
    groups=(
        ("Circuits", (
            _item("wirelesslicenseprofile", "Wireless License Profiles", with_import=True),
            _plain("import_hub", "Import", "add_wirelesslicenseprofile"),
            _plain("pcn_import", "Import from PCN PDF", "add_wirelesslicenseprofile"),
        )),
        ("Catalog", (
            _item("wirelessantenna", "Antennas"),
            _item("wirelesstargetexception", "Target Exceptions"),
            _item("wirelessbandtolerance", "Band Tolerances"),
        )),
        ("LLM Import", (
            _item("wirelessllmprovider", "LLM Providers"),
            _plain("llm_available_models", "Available LLM Models", "view_wirelessllmprovider"),
            _plain("wirelessllmsettings", "LLM Settings", "change_wirelessllmsettings"),
        )),
        ("Settings", (
            _plain("wirelessglobalsettings", "Global Settings", "change_wirelessglobalsettings"),
        )),
    ),
)
