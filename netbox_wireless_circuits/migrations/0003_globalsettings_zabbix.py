from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0002_wirelessglobalsettings_wirelesstargetexception'),
    ]

    operations = [
        migrations.AddField(
            model_name='wirelessglobalsettings',
            name='zabbix_sync_enabled',
            field=models.BooleanField(
                default=False,
                help_text=(
                    "When enabled (and the nbxsync plugin is installed), the "
                    "plugin writes per-link expected values to the receiving "
                    "radio's Zabbix host as user macros via nbxsync. Off by "
                    "default."
                ),
                verbose_name='Zabbix macro sync enabled',
            ),
        ),
        migrations.AddField(
            model_name='wirelessglobalsettings',
            name='zabbix_macro_prefix',
            field=models.CharField(
                default='WL',
                help_text=(
                    "Prefix for the generated Zabbix user macros, e.g. 'WL' "
                    "produces {$WL.RSL.WARN}. Must match the macro names defined "
                    "in your Zabbix wireless template."
                ),
                max_length=50,
                verbose_name='Zabbix macro prefix',
            ),
        ),
        migrations.AddField(
            model_name='wirelessglobalsettings',
            name='zabbix_emit_tags',
            field=models.BooleanField(
                default=True,
                help_text=(
                    "Also attach nbxsync tags to the radio host classifying it "
                    "as a wireless circuit (and its band) for template/trigger "
                    "targeting."
                ),
                verbose_name='Emit Zabbix tags',
            ),
        ),
    ]
