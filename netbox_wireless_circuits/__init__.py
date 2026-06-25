from netbox.plugins import PluginConfig

__version__ = "0.1.0"


class WirelessCircuitsConfig(PluginConfig):
    name = "netbox_wireless_circuits"
    verbose_name = "Wireless Circuits"
    description = (
        "Track licensed microwave and millimeter-wave wireless links as native "
        "NetBox Circuits, with normalized license/PCN, RF endpoint, and "
        "modulation-target design intent."
    )
    version = __version__
    author = "Nextlink Internet"
    author_email = "engineering@nextlinkinternet.com"
    base_url = "wireless-circuits"
    min_version = "4.5.0"
    # No default settings are required; alarm logic lives in Zabbix, not NetBox.
    default_settings = {}

    def ready(self):
        super().ready()
        # The plugin menu is registered via the `menu` object in navigation.py
        # (NetBox's supported PluginMenu API); no manual injection needed.
        # Connect signal receivers that mirror design intent into nbxsync
        # (no-ops unless nbxsync is installed and the sync is enabled).
        from . import signals  # noqa: F401


config = WirelessCircuitsConfig
