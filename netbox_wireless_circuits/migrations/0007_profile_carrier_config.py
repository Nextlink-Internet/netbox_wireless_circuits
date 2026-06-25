from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0006_seed_band_tolerances'),
    ]

    operations = [
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='carrier_count',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='radio_configuration',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
