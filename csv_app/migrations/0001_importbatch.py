import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(name='CSVImportBatch', fields=[
        ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
        ('content', models.TextField()),
        ('row_count', models.PositiveIntegerField()),
        ('completed', models.BooleanField(default=False)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('completed_at', models.DateTimeField(blank=True, null=True)),
        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
    ])]
