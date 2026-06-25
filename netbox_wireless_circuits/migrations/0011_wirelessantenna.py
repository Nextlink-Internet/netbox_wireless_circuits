import django.db.models.deletion
import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('extras', '0134_owner'),
        ('netbox_wireless_circuits', '0010_profile_pcn_document'),
    ]

    operations = [
        migrations.CreateModel(
            name='WirelessAntenna',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('manufacturer', models.CharField(blank=True, max_length=200)),
                ('antenna_code', models.CharField(help_text='Vendor antenna code / part number, e.g. 64664A.', max_length=100)),
                ('model', models.CharField(blank=True, max_length=200)),
                ('diameter_ft', models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True, verbose_name='Diameter (ft)')),
                ('diameter_m', models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True, verbose_name='Diameter (m)')),
                ('gain_dbi', models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True, verbose_name='Gain (dBi)')),
                ('beamwidth_deg', models.DecimalField(blank=True, decimal_places=3, max_digits=7, null=True, verbose_name='Beamwidth (°)')),
                ('polarization', models.CharField(blank=True, max_length=50)),
                ('frequency_range', models.CharField(blank=True, help_text="Operating frequency range, e.g. '17.7-19.7 GHz'.", max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Wireless Antenna',
                'verbose_name_plural': 'Wireless Antennas',
                'ordering': ('manufacturer', 'antenna_code'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='wirelessantenna',
            constraint=models.UniqueConstraint(fields=('manufacturer', 'antenna_code'), name='wwc_antenna_unique_mfr_code'),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='antenna',
            field=models.ForeignKey(blank=True, help_text='Reusable antenna make/model from the antenna catalog.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='endpoints', to='netbox_wireless_circuits.wirelessantenna'),
        ),
    ]
