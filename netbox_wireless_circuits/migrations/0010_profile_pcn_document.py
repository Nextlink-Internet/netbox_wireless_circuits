from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0009_globalsettings_link_type_tag'),
    ]

    operations = [
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='pcn_document',
            field=models.FileField(blank=True, upload_to='netbox-wireless-circuits/pcn/'),
        ),
    ]
