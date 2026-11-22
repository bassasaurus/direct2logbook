from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('profile', '0021_web_reminder_preferences')]
    operations = [migrations.AddField(model_name='reminder', name='ipc_category',
        field=models.CharField(max_length=1, choices=[('A', 'Airplane'), ('R', 'Helicopter')], blank=True, default=''))]
