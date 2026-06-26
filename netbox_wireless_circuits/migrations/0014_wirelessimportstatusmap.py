import taggit.managers
import utilities.json
from django.db import migrations, models

import netbox.models.deletion

# Install defaults: operational circuit status per FCC license status. Operators
# can edit, disable, or delete these afterwards. get_or_create keeps it idempotent.
DEFAULT_STATUS_MAP = [
    ("licensed", "active"),
    ("temporary", "active"),
    ("applied", "planned"),
    ("proposed", "planned"),
    ("transitional", "planned"),
    ("questionable", "planned"),
    ("protection_declined", "planned"),
    ("replaced", "decommissioned"),
    ("expired_terminated", "decommissioned"),
]


def seed_status_map(apps, schema_editor):
    Model = apps.get_model("netbox_wireless_circuits", "WirelessImportStatusMap")
    for license_status, circuit_status in DEFAULT_STATUS_MAP:
        Model.objects.get_or_create(
            license_status=license_status,
            defaults={"circuit_status": circuit_status, "enabled": True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('extras', '0134_owner'),
        ('netbox_wireless_circuits', '0013_endpoint_license_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='WirelessImportStatusMap',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('license_status', models.CharField(max_length=30, unique=True, verbose_name='License status')),
                ('circuit_status', models.CharField(help_text='Operational circuit status applied to imported links whose license status matches.', max_length=50, verbose_name='Circuit status')),
                ('enabled', models.BooleanField(default=True, help_text="If unset, this license status falls back to the import form's default status.")),
                ('notes', models.TextField(blank=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Wireless Import Status Map',
                'verbose_name_plural': 'Wireless Import Status Maps',
                'ordering': ('license_status',),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        # Reverse is a no-op so a rollback never deletes operator-managed rows.
        migrations.RunPython(seed_status_map, migrations.RunPython.noop),
    ]
