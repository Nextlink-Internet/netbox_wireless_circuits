from django.db import migrations

# Sensible install defaults for "acceptable dB off target" per license band.
# Operators can change or delete these afterwards. (80 GHz maps to the 70/80 GHz
# band choice.) get_or_create keeps it idempotent and never clobbers existing rows.
DEFAULT_BAND_TOLERANCES = [
    ("6 GHz", "1.0"),
    ("11 GHz", "1.5"),
    ("18 GHz", "1.5"),
    ("70/80 GHz", "2.0"),
]


def seed_band_tolerances(apps, schema_editor):
    WirelessBandTolerance = apps.get_model(
        "netbox_wireless_circuits", "WirelessBandTolerance"
    )
    for band, tolerance in DEFAULT_BAND_TOLERANCES:
        WirelessBandTolerance.objects.get_or_create(
            frequency_band=band,
            defaults={"tolerance_db": tolerance, "enabled": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ("netbox_wireless_circuits", "0005_wirelessbandtolerance"),
    ]

    operations = [
        # Reverse is a no-op so a rollback never deletes operator-managed rows.
        migrations.RunPython(seed_band_tolerances, migrations.RunPython.noop),
    ]
