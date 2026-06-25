import netbox.models.deletion
import taggit.managers
import utilities.json
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('extras', '0134_owner'),
        ('netbox_wireless_circuits', '0003_globalsettings_zabbix'),
    ]

    operations = [
        migrations.CreateModel(
            name='WirelessLLMSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('pdf_import_enabled', models.BooleanField(default=False, help_text='Enable extracting wireless link fields from an uploaded PCN PDF via an LLM. Requires at least one configured provider with an API key.', verbose_name='PCN PDF import enabled')),
                ('prompt_override', models.TextField(blank=True, help_text='Optional extra instructions appended to the extraction prompt (e.g. notes about your PCN document layout).')),
                ('notes', models.TextField(blank=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Wireless LLM Settings',
                'verbose_name_plural': 'Wireless LLM Settings',
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.CreateModel(
            name='WirelessLLMProvider',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ('created', models.DateTimeField(auto_now_add=True, null=True)),
                ('last_updated', models.DateTimeField(auto_now=True, null=True)),
                ('custom_field_data', models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder)),
                ('rank', models.PositiveIntegerField(default=100, help_text='Lower rank is tried first (1 = primary).')),
                ('provider', models.CharField(choices=[('anthropic', 'Anthropic'), ('gemini', 'Google Gemini'), ('openai', 'OpenAI')], max_length=20)),
                ('model', models.CharField(help_text='Model identifier, e.g. claude-opus-4-8, gemini-2.5-pro, gpt-4.1.', max_length=100)),
                ('enabled', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('tags', taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag')),
            ],
            options={
                'verbose_name': 'Wireless LLM Provider',
                'verbose_name_plural': 'Wireless LLM Providers',
                'ordering': ('rank', 'provider'),
            },
            bases=(netbox.models.deletion.DeleteMixin, models.Model),
        ),
        migrations.AddConstraint(
            model_name='wirelessllmprovider',
            constraint=models.UniqueConstraint(fields=('provider', 'model'), name='wwc_llmprovider_unique_provider_model'),
        ),
    ]
