from django.db import migrations, models
import django.utils.timezone


def mark_completed(apps, schema_editor):
    Batch = apps.get_model('csv_app', 'CSVImportBatch')
    Batch.objects.filter(completed=True).update(status='completed')


class Migration(migrations.Migration):
    dependencies = [('csv_app', '0001_importbatch')]
    operations = [
        migrations.AddField(model_name='csvimportbatch', name='status', field=models.CharField(choices=[('preview', 'Preview'), ('queued', 'Queued'), ('unconfirmed', 'Queue unconfirmed'), ('processing', 'Importing'), ('completed', 'Completed'), ('failed', 'Failed')], db_index=True, default='preview', max_length=20)),
        migrations.AddField(model_name='csvimportbatch', name='task_id', field=models.CharField(blank=True, max_length=255, null=True)),
        migrations.AddField(model_name='csvimportbatch', name='submitted_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='csvimportbatch', name='started_at', field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='csvimportbatch', name='updated_at', field=models.DateTimeField(default=django.utils.timezone.now)),
        migrations.AddField(model_name='csvimportbatch', name='error_message', field=models.TextField(blank=True)),
        migrations.RunPython(mark_completed, migrations.RunPython.noop),
    ]
