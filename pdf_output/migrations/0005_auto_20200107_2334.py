import datetime
from django.db import migrations, models
from datetime import timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pdf_output', '0004_auto_20200107_0008'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='signature',
            options={'get_latest_by': ['signature'],
                     'ordering': ['-date', 'user']},
        ),
        migrations.AlterField(
            model_name='signature',
            name='date',
            field=models.DateField(db_index=True, default=datetime.datetime(
                2020, 1, 7, 23, 34, 1, 800668, tzinfo=timezone.utc)),
        ),
    ]
