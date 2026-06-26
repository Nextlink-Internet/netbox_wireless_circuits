from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0012_profile_import_source_key'),
    ]

    operations = [
        migrations.AlterField(
            model_name='wirelesslicenseprofile',
            name='registration_status',
            field=models.CharField(blank=True, default='unknown', help_text='Link-level FCC license status. Rolled up from the two ends on import (the more attention-worthy status wins); see each endpoint for its own license status.', max_length=30, verbose_name='License status'),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='license_status',
            field=models.CharField(blank=True, help_text="This end's FCC license status (e.g. Licensed, Applied).", max_length=30, verbose_name='License status'),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='license_basis',
            field=models.CharField(blank=True, help_text='Primary or Secondary (co-primary) license basis.', max_length=20, verbose_name='License basis'),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='conditional_authorization',
            field=models.BooleanField(default=False, verbose_name='Conditional authorization'),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='license_application_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='license_effective_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='wirelesscircuitendpoint',
            name='license_expiration_date',
            field=models.DateField(blank=True, null=True, help_text="License expiry for this end; the link's earliest is used for renewal tracking."),
        ),
    ]
