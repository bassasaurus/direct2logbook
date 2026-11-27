from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('flights', '0081_validate_flight_remarks')]
    operations = [migrations.AddField(
        model_name='flight', name='night_landings_full_stop',
        field=models.BooleanField(blank=True, default=None, null=True),
    )]
