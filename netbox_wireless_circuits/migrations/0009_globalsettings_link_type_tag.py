from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0008_profile_created_via_import'),
    ]

    operations = [
        migrations.AddField(
            model_name='wirelessglobalsettings',
            name='link_type_tag_enabled',
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name='wirelessglobalsettings',
            name='link_type_tag_template',
            field=models.CharField(default='link_type: {config}', max_length=100),
        ),
    ]
