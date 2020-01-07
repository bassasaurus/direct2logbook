# Generated by Django 2.2.8 on 2020-01-07 00:08

import datetime
from django.db import migrations, models
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('pdf_output', '0003_signature_user'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='signature',
            options={'ordering': ['-date', 'user']},
        ),
        migrations.AddField(
            model_name='signature',
            name='date',
            field=models.DateField(db_index=True, default=datetime.datetime(2020, 1, 7, 0, 8, 30, 403115, tzinfo=utc)),
        ),
    ]