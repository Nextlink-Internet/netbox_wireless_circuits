from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0007_profile_carrier_config'),
    ]

    operations = [
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='created_via_import',
            field=models.BooleanField(default=False),
        ),
    ]
