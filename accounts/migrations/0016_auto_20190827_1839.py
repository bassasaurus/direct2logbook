# Generated by Django 2.2.4 on 2019-08-27 18:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0015_auto_20190826_2134'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='trial_end',
            field=models.DateField(blank=True, default=None, null=True),
        ),
    ]