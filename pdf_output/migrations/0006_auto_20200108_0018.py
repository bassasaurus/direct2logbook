# Generated by Django 2.2.8 on 2020-01-08 00:18

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('pdf_output', '0005_auto_20200107_2334'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='signature',
            options={'get_latest_by': ['signature'], 'ordering': ['-created_at', 'user']},
        ),
        migrations.RemoveField(
            model_name='signature',
            name='date',
        ),
        migrations.AddField(
            model_name='signature',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='signature',
            name='updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
