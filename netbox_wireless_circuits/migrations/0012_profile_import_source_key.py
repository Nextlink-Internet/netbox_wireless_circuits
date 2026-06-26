from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_wireless_circuits', '0011_wirelessantenna'),
    ]

    operations = [
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='import_source',
            field=models.CharField(blank=True, help_text="External data source this link was imported from, e.g. 'comsearch'.", max_length=50, verbose_name='Import source'),
        ),
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='import_key',
            field=models.CharField(blank=True, db_index=True, help_text='Stable per-link de-duplication key within the import source; a re-upload updates the matching link instead of duplicating it.', max_length=200, verbose_name='Import key'),
        ),
        migrations.AddField(
            model_name='wirelesslicenseprofile',
            name='import_link_id',
            field=models.CharField(blank=True, help_text="The source's own link identifier, retained for traceability.", max_length=100, verbose_name='Import link ID'),
        ),
        migrations.AddConstraint(
            model_name='wirelesslicenseprofile',
            constraint=models.UniqueConstraint(condition=models.Q(import_key__gt=''), fields=('import_source', 'import_key'), name='wwc_profile_unique_import_source_key'),
        ),
    ]
