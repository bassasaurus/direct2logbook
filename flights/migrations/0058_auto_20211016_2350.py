# Generated by Django 3.1.1 on 2021-10-16 23:50

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0057_auto_20210823_1747'),
    ]

    operations = [
        migrations.AlterField(
            model_name='holding',
            name='hold',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
