import uuid
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    # Legacy 0001-0007 files were removed, but deployed databases retain their
    # migration records. Use a new name and a self-contained current-model baseline.
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [migrations.CreateModel(
        name='PDFRequest',
        fields=[
            ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
            ('task_id', models.CharField(max_length=255, unique=True)),
            ('status', models.CharField(choices=[('queued', 'Queued'), ('unconfirmed', 'Submission unconfirmed'), ('processing', 'Processing'), ('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed'), ('delivery_uncertain', 'Delivery uncertain')], default='queued', max_length=24)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('updated_at', models.DateTimeField(auto_now=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
        ],
        options={'ordering': ['-created_at']},
    )]
