# Generated by Django 2.2.8 on 2019-12-27 02:33

from django.db import migrations, models
import pdf_output.models


class Migration(migrations.Migration):

    dependencies = [
        ('pdf_output', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='signature',
            name='signature',
            field=models.ImageField(upload_to=pdf_output.models.user_directory_path),
        ),
    ]
