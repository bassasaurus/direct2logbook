from django.db import migrations, models
import signature_pad.fields


class Migration(migrations.Migration):
    dependencies = [('signature', '0005_alter_signature_user')]
    operations = [
        migrations.AlterField(model_name='signature', name='signature',
            field=signature_pad.fields.SignaturePadField(blank=True, null=True)),
        migrations.AddField(model_name='signature', name='encrypted_data',
            field=models.TextField(blank=True, default='', editable=False)),
    ]
