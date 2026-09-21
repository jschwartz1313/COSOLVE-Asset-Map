from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name="CompletedRelease",
            fields=[
                ("version", models.CharField(max_length=64, primary_key=True, serialize=False)),
                ("completed_at", models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
