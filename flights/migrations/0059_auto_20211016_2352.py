# Generated by Django 3.1.1 on 2021-10-16 23:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0058_auto_20211016_2350'),
    ]

    operations = [
        migrations.AlterField(
            model_name='holding',
            name='hold',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]