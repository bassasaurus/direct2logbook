from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('pdf_output', '0008_pdfrequest')]
    operations = [
        migrations.AddField(
            model_name='pdfrequest', name='render_attempts',
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name='pdfrequest', name='status',
            field=models.CharField(choices=[('queued', 'Queued'), ('unconfirmed', 'Submission unconfirmed'), ('processing', 'Processing'), ('retrying', 'Retrying'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed'), ('delivery_uncertain', 'Delivery uncertain')], default='queued', max_length=24),
        ),
    ]
