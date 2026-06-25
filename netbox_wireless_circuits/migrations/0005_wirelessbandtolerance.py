import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('extras', '0134_owner'),
        ('netbox_wireless_circuits', '0004_llm_settings_provider'),
    ]

    operations = [
        migrations.CreateModel(
            name='WirelessBandTolerance',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('frequency_band', models.CharField(choices=[('6 GHz', '6 GHz'), ('11 GHz', '11 GHz'), ('18 GHz', '18 GHz'), ('23 GHz', '23 GHz'), ('70/80 GHz', '70/80 GHz'), ('90 GHz', '90 GHz')], help_text='License band this tolerance rule applies to.', max_length=20, unique=True)),
                ('tolerance_db', models.DecimalField(decimal_places=2, default=0, help_text="Allowed dB off the PCN target for this band, added to each modulation target's warning/critical margins. 0 means the link must meet target.", max_digits=6, verbose_name='Tolerance (dB)')),
                ('enabled', models.BooleanField(default=True, help_text='If unset, links in this band fall back to the default tolerance.')),
                ('notes', models.TextField(blank=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Wireless Band Tolerance',
                'verbose_name_plural': 'Wireless Band Tolerances',
                'ordering': ('frequency_band',),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
    ]
