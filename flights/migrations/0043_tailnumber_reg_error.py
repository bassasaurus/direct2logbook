# Generated by Django 2.2.4 on 2019-11-25 23:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0042_remove_tailnumber_reg_error'),
    ]

    operations = [
        migrations.AddField(
            model_name='tailnumber',
            name='reg_error',
            field=models.BooleanField(default=False),
        ),
    ]
